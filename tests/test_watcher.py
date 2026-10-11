from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from fake_clock import FakeClock

from catpoop import observations as obs
from catpoop.config import VisitSettings
from catpoop.domain import Detection, Event, Frame, Outcome, OutcomeScores, Urgency
from catpoop.interfaces import CameraLoginExpired
from catpoop.parts.memory_event_log import MemoryEventLog
from catpoop.visits.store import VisitStore
from catpoop.watcher.recorder import LiveVisitRecorder
from catpoop.watcher.watcher import Watcher

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


class BrokenRecorder(LiveVisitRecorder):
    def save(self, now):
        super().discard()
        raise OSError("NAS is not mounted")


class Run:
    def __init__(self, tmp_path, script, model=None, recorder=None, detect_seconds=0.0) -> None:
        self.clock = FakeClock(START)
        self.rules = RecordingRules()
        self.log = MemoryEventLog()
        self.store = tmp_path / "store"
        self.watcher = Watcher(
            camera=ScriptedCamera(script, self.clock),
            detector=FakeDetector(self.clock, detect_seconds),
            rules=self.rules,
            event_log=self.log,
            recorder=recorder or LiveVisitRecorder(self.store, SETTINGS, tmp_path / "temp"),
            clock=self.clock,
            visits=SETTINGS,
            offline_after=timedelta(seconds=10),
            check_seconds=1,
            outcome_model=model,
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


def test_run_checks_every_check_seconds_until_stopped(tmp_path):
    run = Run(tmp_path, "....", detect_seconds=0.25)
    checks = iter(range(4))
    run.watcher.run(stop=lambda: next(checks, None) is None)
    assert len(run.rules.seen) == 4
    assert run.clock.slept == pytest.approx([0.75] * 4)


def test_login_expired_is_not_also_camera_offline(tmp_path):
    run = Run(tmp_path, "L" * 12).step_through(12)
    assert run.said() == [(0, "LoginExpired")]
