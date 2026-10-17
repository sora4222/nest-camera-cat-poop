from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pytest
from fake_clock import FakeClock

from catpoop import observations as obs
from catpoop.communications.switches import Switches
from catpoop.config import Household, QuietHours, VisitSettings
from catpoop.domain import Detection, Event, Frame, Outcome, OutcomeScores, Presence, Urgency
from catpoop.interfaces import CameraLoginExpired
from catpoop.parts.memory_event_log import MemoryEventLog
from catpoop.parts.standard_communications import RoutedSpeaker, StandardCommunications
from catpoop.visits.store import VisitStore
from catpoop.watcher.recorder import LiveVisitRecorder
from catpoop.watcher.watcher import SAY_WAIT_SECONDS, Watcher

START = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)
SETTINGS = VisitSettings(end_gap_seconds=3, min_seconds=2, padding_seconds=1, frame_seconds=1)
CAT, EMPTY = 255, 0


class ScriptedCamera:
    """One character per read: `C` the Cat in the box, `.` an empty box, `-` no picture,
    `L` Login Expired."""

    def __init__(self, script: str, clock: FakeClock) -> None:
        self._script = iter(script)
        self._clock = clock

    def read(self) -> Frame | None:
        step = next(self._script)
        if step == "L":
            raise CameraLoginExpired("refused")
        if step == "-":
            return None
        value = CAT if step == "C" else EMPTY
        return Frame(self._clock.now(), np.full((48, 64, 3), value, np.uint8))


class FakeDetector:
    def __init__(self, clock: FakeClock, seconds: float = 0) -> None:
        self._clock = clock
        self._seconds = seconds

    def detect(self, frame: Frame) -> list[Detection]:
        self._clock.advance(self._seconds)
        if frame.image.mean() > 128:
            return [Detection("cat", 0.9, (0.4, 0.4, 0.6, 0.6))]
        return []


def scores(best: Outcome) -> OutcomeScores:
    return OutcomeScores({o: 1.0 if o is best else 0.0 for o in Outcome})


class FakeOutcomeModel:
    """Guesses Poop, decides Pee; remembers the frames it was given."""

    def __init__(self) -> None:
        self.guessed: list[Frame] = []
        self.decided: list[Frame] = []

    def guess(self, stance: Frame) -> OutcomeScores:
        self.guessed.append(stance)
        return scores(Outcome.POOP)

    def outcome(self, surface: Frame) -> OutcomeScores:
        self.decided.append(surface)
        return scores(Outcome.PEE)


class RecordingRules:
    def __init__(self) -> None:
        self.seen: list[obs.Observation] = []

    def update(self, observation: obs.Observation) -> list[Event]:
        self.seen.append(observation)
        if isinstance(observation, obs.Seen | obs.NoPicture):
            return []
        return [Event(type(observation).__name__, Urgency.INFO, observation.at)]


class RecordingCommunications:
    def __init__(self) -> None:
        self.handled: list[Event] = []
        self.ticks: list[datetime] = []
        self.closed: list[float] = []

    def handle(self, event: Event) -> None:
        self.handled.append(event)

    def tick(self, at: datetime) -> None:
        self.ticks.append(at)

    def close(self, seconds: float) -> bool:
        self.closed.append(seconds)
        return True


class BrokenRecorder(LiveVisitRecorder):
    def save(self, now):
        super().discard()
        raise OSError("NAS is not mounted")


class Run:
    def __init__(
        self,
        tmp_path,
        script,
        model=None,
        recorder=None,
        detect_seconds=0.0,
        detector=None,
        surface_seconds=1000.0,
        communications=None,
        rules=None,
    ) -> None:
        self.clock = FakeClock(START)
        self.rules = rules or RecordingRules()
        self.log = MemoryEventLog()
        self.communications = communications or RecordingCommunications()
        self.store = tmp_path / "store"
        self.watcher = Watcher(
            camera=ScriptedCamera(script, self.clock),
            detector=detector(self.clock) if detector else FakeDetector(self.clock, detect_seconds),
            rules=self.rules,
            event_log=self.log,
            communications=self.communications,
            recorder=recorder or LiveVisitRecorder(self.store, SETTINGS, tmp_path / "temp"),
            clock=self.clock,
            visits=SETTINGS,
            offline_after=timedelta(seconds=10),
            check_seconds=1,
            outcome_model=model,
            surface_check_seconds=surface_seconds,
        )

    def step_through(self, steps: int) -> "Run":
        for _ in range(steps):
            self.watcher.step()
            self.clock.advance(1)
        return self

    def said(self) -> list[tuple[float, str]]:
        """Observations other than Seen and NoPicture, as (seconds from start, name)."""
        return [
            ((o.at - START).total_seconds(), type(o).__name__)
            for o in self.rules.seen
            if not isinstance(o, obs.Seen | obs.NoPicture)
        ]

    def first(self, kind: type) -> obs.Observation:
        return next(o for o in self.rules.seen if isinstance(o, kind))


def test_every_check_is_seen_or_no_picture(tmp_path):
    run = Run(tmp_path, "C-.").step_through(3)
    seen = run.rules.seen
    assert [type(o).__name__ for o in seen] == ["Seen", "NoPicture", "Seen"]
    assert isinstance(seen[0], obs.Seen)
    assert [d.label for d in seen[0].detections] == ["cat"]


def test_a_visit_starts_and_ends_with_the_outcome_guess_and_outcome(tmp_path):
    model = FakeOutcomeModel()
    run = Run(tmp_path, "..CCCC.....", model).step_through(11)
    assert run.said() == [(4, "VisitStarted"), (9, "VisitEnded")]
    started = run.first(obs.VisitStarted)
    assert isinstance(started, obs.VisitStarted)
    assert [(f.taken_at - START).total_seconds() for f in started.frames] == [2, 3, 4]
    assert started.guess == scores(Outcome.POOP)
    assert model.guessed == [started.frames[-1]]
    ended = run.first(obs.VisitEnded)
    assert isinstance(ended, obs.VisitEnded)
    assert ended.started_at == started.at
    assert [(f.taken_at - START).total_seconds() for f in ended.frames] == [6, 7, 8, 9]
    assert ended.outcome == scores(Outcome.PEE)
    assert model.decided == [ended.frames[-1]]


def test_each_visit_is_saved_for_labeling(tmp_path):
    run = Run(tmp_path, "..CCCC.....").step_through(11)
    ended = run.first(obs.VisitEnded)
    assert isinstance(ended, obs.VisitEnded)
    [visit] = VisitStore(run.store).unlabeled()
    assert (ended.saved_visit, visit.source) == (visit.id, "live")
    # From one second before the Cat was first seen until the Visit ended.
    assert visit.recorded_at == (START + timedelta(seconds=1)).isoformat()
    assert visit.frames == 9


def test_a_cat_coming_back_is_not_part_of_the_visit_that_ended(tmp_path):
    model = FakeOutcomeModel()
    run = Run(tmp_path, "CCC...CCC", model).step_through(9)
    assert run.said() == [(2, "VisitStarted"), (6, "VisitEnded"), (8, "VisitStarted")]
    ended = run.first(obs.VisitEnded)
    assert isinstance(ended, obs.VisitEnded)
    assert [(f.taken_at - START).total_seconds() for f in ended.frames] == [3, 4, 5]
    assert model.decided == [ended.frames[-1]]
    [visit] = VisitStore(run.store).unlabeled()
    assert visit.frames == 6


def test_no_outcome_model_means_no_scores(tmp_path):
    run = Run(tmp_path, "..CCCC.....").step_through(11)
    started, ended = run.first(obs.VisitStarted), run.first(obs.VisitEnded)
    assert isinstance(started, obs.VisitStarted) and isinstance(ended, obs.VisitEnded)
    assert (started.guess, ended.outcome) == (None, None)


def test_a_visit_that_cannot_be_saved_still_ends(tmp_path, caplog):
    recorder = BrokenRecorder(tmp_path / "store", SETTINGS, tmp_path / "temp")
    run = Run(tmp_path, "..CCCC.....", recorder=recorder).step_through(11)
    ended = run.first(obs.VisitEnded)
    assert isinstance(ended, obs.VisitEnded)
    assert ended.saved_visit is None
    assert "NAS is not mounted" in caplog.text


def test_camera_offline_once_per_outage(tmp_path):
    run = Run(tmp_path, "." + "-" * 12 + "." + "-" * 12).step_through(26)
    assert run.said() == [(10, "CameraOffline"), (23, "CameraOffline")]
    offline = run.first(obs.CameraOffline)
    assert isinstance(offline, obs.CameraOffline)
    assert offline.since == START


def test_camera_offline_ends_the_visit_going_on(tmp_path):
    model = FakeOutcomeModel()
    run = Run(tmp_path, "CCC" + "-" * 10, model).step_through(13)
    assert run.said() == [(2, "VisitStarted"), (12, "CameraOffline"), (12, "VisitEnded")]
    ended = run.first(obs.VisitEnded)
    assert isinstance(ended, obs.VisitEnded)
    assert (ended.frames, ended.outcome, model.decided) == ((), None, [])
    assert ended.saved_visit is not None


def test_login_expired_once_until_pictures_come_back(tmp_path):
    run = Run(tmp_path, "LLL.L").step_through(5)
    assert run.said() == [(0, "LoginExpired"), (4, "LoginExpired")]


def test_events_from_the_rules_go_in_the_event_log(tmp_path):
    run = Run(tmp_path, "L").step_through(1)
    assert [e.kind for e in run.log.recent(10)] == ["LoginExpired"]


def test_every_event_goes_to_the_communications_handler_which_ticks_each_check(tmp_path):
    run = Run(tmp_path, "L.").step_through(2)
    assert [e.kind for e in run.communications.handled] == ["LoginExpired"]
    assert run.communications.ticks == [START, START + timedelta(seconds=1)]


def test_run_checks_every_check_seconds_until_stopped(tmp_path):
    run = Run(tmp_path, "....", detect_seconds=0.25)
    checks = iter(range(4))
    run.watcher.run(stop=lambda: next(checks, None) is None)
    assert len(run.rules.seen) == 4
    assert run.clock.slept == pytest.approx([0.75] * 4)


def test_login_expired_is_not_also_camera_offline(tmp_path):
    run = Run(tmp_path, "L" * 12).step_through(12)
    assert run.said() == [(0, "LoginExpired")]


class FlakyDetector(FakeDetector):
    """Fails on the frames in `broken` (by read number), works on the others."""

    def __init__(self, clock: FakeClock, broken: set[int]) -> None:
        super().__init__(clock)
        self._broken = broken
        self._calls = 0

    def detect(self, frame: Frame) -> list[Detection]:
        self._calls += 1
        if self._calls in self._broken:
            raise RuntimeError("detector blew up")
        return super().detect(frame)


def test_a_detector_failure_is_logged_and_the_watcher_keeps_going(tmp_path, caplog):
    flaky = lambda clock: FlakyDetector(clock, {2})  # noqa: E731
    run = Run(tmp_path, "..CCCC.....", detector=flaky).step_through(11)
    assert "detector blew up" in caplog.text
    assert [type(o).__name__ for o in run.rules.seen[:3]] == ["Seen", "NoPicture", "Seen"]
    assert run.said() == [(4, "VisitStarted"), (9, "VisitEnded")]


def test_stopping_during_a_visit_discards_the_recording(tmp_path):
    run = Run(tmp_path, "..CCCC")
    checks = iter(range(6))
    run.watcher.run(stop=lambda: next(checks, None) is None)
    assert run.said() == [(4, "VisitStarted")]
    assert list((tmp_path / "temp").iterdir()) == []


def test_ctrl_c_during_a_visit_discards_the_recording(tmp_path):
    run = Run(tmp_path, "..CCCC")
    checks = iter(range(6))

    def stop() -> bool:
        if next(checks, None) is None:
            raise KeyboardInterrupt
        return False

    with pytest.raises(KeyboardInterrupt):
        run.watcher.run(stop=stop)
    assert list((tmp_path / "temp").iterdir()) == []


def test_stopping_gives_the_speakers_time_to_say_what_they_were_given(tmp_path):
    run = Run(tmp_path, "..")

    def stop() -> bool:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run.watcher.run(stop=stop)
    assert run.communications.closed == [SAY_WAIT_SECONDS]


def test_the_litter_surface_is_checked_now_and_then_while_the_box_is_empty(tmp_path):
    model = FakeOutcomeModel()
    run = Run(tmp_path, "...C......", model, surface_seconds=3).step_through(10)
    surfaces = {
        (o.at - START).total_seconds(): o.surface for o in run.rules.seen if isinstance(o, obs.Seen)
    }
    assert [s for s, surface in surfaces.items() if surface] == [4, 7]
    assert surfaces[4] == scores(Outcome.PEE)
    assert len(model.decided) == 2


def test_no_outcome_model_means_no_surface_checks(tmp_path):
    run = Run(tmp_path, "......", surface_seconds=1).step_through(6)
    assert all(o.surface is None for o in run.rules.seen if isinstance(o, obs.Seen))


class BrokenOutcomeModel(FakeOutcomeModel):
    def outcome(self, surface: Frame) -> OutcomeScores:
        raise RuntimeError("model blew up")


def test_a_failed_surface_check_is_logged_and_skipped(tmp_path, caplog):
    run = Run(tmp_path, "....", BrokenOutcomeModel(), surface_seconds=1).step_through(4)
    assert "model blew up" in caplog.text
    assert len([o for o in run.rules.seen if isinstance(o, obs.Seen)]) == 4


class BrokenCommunications(RecordingCommunications):
    def handle(self, event: Event) -> None:
        raise RuntimeError("presence check is down")

    def tick(self, at: datetime) -> None:
        raise RuntimeError("presence check is down")


def test_a_communications_failure_is_logged_and_the_watcher_keeps_going(tmp_path, caplog):
    run = Run(tmp_path, "L..", communications=BrokenCommunications()).step_through(3)
    assert [e.kind for e in run.log.recent(10)] == ["LoginExpired"]
    assert len(run.rules.seen) == 4
    assert "communications" in caplog.text


DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class SayingSpeaker:
    name = "Living room"

    def __init__(self) -> None:
        self.said: list[str] = []

    def say(self, text: str) -> None:
        self.said.append(text)


class UnknownPresence:
    def check(self, listener: str) -> Presence:
        return Presence.UNKNOWN


class PoopRules(RecordingRules):
    """Sees Poop on the picture at `at`."""

    def __init__(self, at: datetime) -> None:
        super().__init__()
        self._at = at

    def update(self, observation: obs.Observation) -> list[Event]:
        super().update(observation)
        if isinstance(observation, obs.Seen) and observation.at == self._at:
            return [Event("poop", Urgency.NORMAL, observation.at)]
        return []


def test_poop_seen_on_the_first_check_after_quiet_hours_is_said_once(tmp_path):
    speaker = SayingSpeaker()
    communications = StandardCommunications(
        speakers=[RoutedSpeaker(speaker, frozenset(Urgency))],
        presence=UnknownPresence(),
        listeners=[],
        quiet_hours=[QuietHours(days=[*DAYS], start=time(7), end=time(8, 0, 1))],
        zone=ZoneInfo("UTC"),
        messages={"poop": "Poop.", "poop_after_quiet_hours": "Poop from the night."},
        household=Household(cat="Cat", dog="Dog"),
        switches=Switches(tmp_path / "switches.json"),
    )
    rules = PoopRules(START + timedelta(seconds=1))  # Quiet Hours end at 08:00:01
    Run(tmp_path, "..", communications=communications, rules=rules).step_through(2)
    assert communications.close(5)
    assert speaker.said == ["Poop."]


class GuessBlowsUp(FakeOutcomeModel):
    def guess(self, stance: Frame) -> OutcomeScores:
        raise RuntimeError("guess blew up")


class OutcomeBlowsUp(FakeOutcomeModel):
    def outcome(self, surface: Frame) -> OutcomeScores:
        raise RuntimeError("outcome blew up")


def test_a_failed_outcome_guess_is_logged_and_the_visit_goes_on(tmp_path, caplog):
    run = Run(tmp_path, "..CCCC.....", GuessBlowsUp()).step_through(11)
    assert "guess blew up" in caplog.text
    assert run.said() == [(4, "VisitStarted"), (9, "VisitEnded")]
    started, ended = run.first(obs.VisitStarted), run.first(obs.VisitEnded)
    assert isinstance(started, obs.VisitStarted) and isinstance(ended, obs.VisitEnded)
    assert (started.guess, ended.outcome) == (None, scores(Outcome.PEE))


def test_a_failed_outcome_is_logged_and_the_visit_still_ends(tmp_path, caplog):
    run = Run(tmp_path, "..CCCC.....", OutcomeBlowsUp()).step_through(11)
    assert "outcome blew up" in caplog.text
    ended = run.first(obs.VisitEnded)
    assert isinstance(ended, obs.VisitEnded)
    assert ended.outcome is None
    assert ended.saved_visit is not None


class StartBlowsUp(LiveVisitRecorder):
    def start(self, frames):
        raise RuntimeError("no room for the clip")


def test_a_recording_that_cannot_start_is_logged_and_the_visit_goes_on(tmp_path, caplog):
    recorder = StartBlowsUp(tmp_path / "store", SETTINGS, tmp_path / "temp")
    run = Run(tmp_path, "..CCCC.....CCCC.....", recorder=recorder).step_through(20)
    assert "no room for the clip" in caplog.text
    assert [name for _, name in run.said()] == ["VisitStarted", "VisitEnded"] * 2
    ended = run.first(obs.VisitEnded)
    assert isinstance(ended, obs.VisitEnded)
    assert ended.saved_visit is None


class AddBlowsUp(LiveVisitRecorder):
    """Records the frames from before the Visit, then fails on the next one."""

    adding_later = False

    def start(self, frames):
        super().start(frames)
        self.adding_later = True

    def add(self, frame):
        if self.adding_later and self.recording:
            raise OSError("disk full")
        super().add(frame)


def test_a_recording_that_fails_midway_is_dropped_and_the_visit_goes_on(tmp_path, caplog):
    recorder = AddBlowsUp(tmp_path / "store", SETTINGS, tmp_path / "temp")
    run = Run(tmp_path, "..CCCC.....", recorder=recorder).step_through(11)
    assert "disk full" in caplog.text
    assert run.said() == [(4, "VisitStarted"), (9, "VisitEnded")]
    ended = run.first(obs.VisitEnded)
    assert isinstance(ended, obs.VisitEnded)
    assert ended.saved_visit is None
    assert list((tmp_path / "temp").iterdir()) == []


class CloseWatchingRecorder(LiveVisitRecorder):
    closed = 0

    def close(self) -> None:
        self.closed += 1
        super().close()


def test_stopping_closes_the_recorder(tmp_path):
    recorder = CloseWatchingRecorder(tmp_path / "store", SETTINGS, tmp_path / "temp")
    run = Run(tmp_path, "....", recorder=recorder)
    checks = iter(range(2))
    run.watcher.run(stop=lambda: next(checks, None) is None)
    assert recorder.closed == 1
