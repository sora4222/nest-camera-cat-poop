"""The live watcher loop: read the camera, run the detector, follow Visits, tell the event rules.

Each check hands the event rules one observation (`Seen` or `NoPicture`), plus Visit starts
and ends, Camera Offline and Login Expired when they happen. The Events the rules give back
go in the event log.
"""

import logging
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta

from catpoop import observations as obs
from catpoop.clock import Clock
from catpoop.config import VisitSettings
from catpoop.domain import Frame
from catpoop.interfaces import (
    CameraLoginExpired,
    CameraSource,
    Detector,
    EventLog,
    EventRules,
    OutcomeModel,
)
from catpoop.visits.finder import VisitEnded, VisitStarted, VisitTracker, cat_in_litter_box
from catpoop.visits.video import VideoError
from catpoop.watcher.recorder import LiveVisitRecorder

log = logging.getLogger(__name__)


class Watcher:
    """Checks the camera once per `step`; `run` steps every `check_seconds`."""

    def __init__(
        self,
        *,
        camera: CameraSource,
        detector: Detector,
        rules: EventRules,
        event_log: EventLog,
        recorder: LiveVisitRecorder,
        clock: Clock,
        visits: VisitSettings,
        offline_after: timedelta,
        check_seconds: float,
        outcome_model: OutcomeModel | None = None,
    ) -> None:
        """`offline_after` with no picture is Camera Offline. No `outcome_model`, no scores."""
        self._camera = camera
        self._detector = detector
        self._rules = rules
        self._event_log = event_log
        self._recorder = recorder
        self._clock = clock
        self._visits = visits
        self._offline_after = offline_after
        self._check_seconds = check_seconds
        self._outcome_model = outcome_model
        self._started = clock.now()
        self._tracker = VisitTracker(visits)
        self._recent: deque[Frame] = deque()
        self._keep = timedelta(
            seconds=visits.min_seconds + visits.end_gap_seconds + visits.padding_seconds
        )
        self._visit_started_at: datetime | None = None
        self._last_picture = self._started
        self._offline_said = False
        self._login_said = False

    def run(self, stop: Callable[[], bool] = lambda: False) -> None:
        """Check every `check_seconds` until `stop()` is true; drops an unfinished Visit's clip."""
        try:
            while not stop():
                began = self._clock.now()
                self.step()
                used = (self._clock.now() - began).total_seconds()
                self._clock.sleep(max(0.0, self._check_seconds - used))
        finally:
            self._recorder.discard()

    def step(self) -> None:
        """Read the camera once and pass on what was seen."""
        now = self._clock.now()
        try:
            frame = self._camera.read()
        except CameraLoginExpired as error:
            frame = None
            if not self._login_said:
                log.error("camera login expired: %s", error)
                self._login_said = True
                self._tell(obs.LoginExpired(now))
        if frame is None:
            self._no_picture(now)
        else:
            self._picture(now, frame)

    def _no_picture(self, now: datetime) -> None:
        if not self._offline_said and now - self._last_picture >= self._offline_after:
            self._offline_said = True
            if not self._login_said:
                self._tell(obs.CameraOffline(now, self._last_picture))
            ended = self._tracker.finish()
            if ended:
                self._end_visit(now, ())
        self._tell(obs.NoPicture(now))

    def _picture(self, now: datetime, frame: Frame) -> None:
        self._last_picture = now
        self._offline_said = self._login_said = False
        try:
            detections = tuple(self._detector.detect(frame))
        except Exception:
            log.exception("the detector failed; skipping this picture")
            self._tell(obs.NoPicture(now))
            return
        self._tell(obs.Seen(now, frame, detections))
        self._recent.append(frame)
        while self._recent and frame.taken_at - self._recent[0].taken_at > self._keep:
            self._recent.popleft()
        self._recorder.add(frame)
        seen = cat_in_litter_box(detections, self._visits)
        for change in self._tracker.see(self._seconds(frame.taken_at), seen):
            match change:
                case VisitStarted(first_seen=first):
                    self._start_visit(now, first)
                case VisitEnded(span=span):
                    last_seen = span.end - self._visits.padding_seconds
                    self._end_visit(now, self._frames_since(last_seen, after=True))

    def _start_visit(self, now: datetime, first_seen: float) -> None:
        self._visit_started_at = now
        self._recorder.start(self._frames_since(first_seen - self._visits.padding_seconds))
        frames = self._frames_since(first_seen)
        guess = self._outcome_model.guess(frames[-1]) if self._outcome_model else None
        self._tell(obs.VisitStarted(now, frames, guess))

    def _end_visit(self, now: datetime, frames: tuple[Frame, ...]) -> None:
        outcome = None
        if self._outcome_model and frames:
            outcome = self._outcome_model.outcome(frames[-1])
        saved = None
        try:
            saved = self._recorder.save(now).id
        except (OSError, VideoError) as error:
            log.error("could not save the Visit: %s", error)
            self._recorder.discard()
        self._tell(obs.VisitEnded(now, self._visit_started_at or now, frames, outcome, saved))
        self._visit_started_at = None

    def _frames_since(self, seconds: float, after: bool = False) -> tuple[Frame, ...]:
        """Recent frames from `seconds` on (or only later ones with `after`)."""
        return tuple(
            f
            for f in self._recent
            if (s := self._seconds(f.taken_at)) > seconds or (not after and s == seconds)
        )

    def _seconds(self, at: datetime) -> float:
        return (at - self._started).total_seconds()

    def _tell(self, observation: obs.Observation) -> None:
        for event in self._rules.update(observation):
            self._event_log.record(event)
