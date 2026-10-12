"""What the live watcher sees, handed to the event rules one at a time."""

from dataclasses import dataclass
from datetime import datetime

from catpoop.domain import Detection, Frame, OutcomeScores


@dataclass(frozen=True)
class Seen:
    """A Frame the detector has checked, with what it found."""

    at: datetime
    frame: Frame
    detections: tuple[Detection, ...]


@dataclass(frozen=True)
class NoPicture:
    """The camera gave no new Frame this time."""

    at: datetime


@dataclass(frozen=True)
class VisitStarted:
    """A Visit has started; `frames` show the Cat in the Litter Box."""

    at: datetime
    frames: tuple[Frame, ...]
    guess: OutcomeScores | None
    """The Outcome Guess; None when there is no Outcome model yet."""


@dataclass(frozen=True)
class VisitEnded:
    """The Visit that started at `started_at` is over; `frames` show the litter surface after."""

    at: datetime
    started_at: datetime
    frames: tuple[Frame, ...]
    outcome: OutcomeScores | None
    """None when there is no Outcome model yet."""
    saved_visit: str | None
    """Id of the Visit saved in the Private Data Store; None if saving failed."""


@dataclass(frozen=True)
class CameraOffline:
    """No picture since `since`, for the Camera Offline time."""

    at: datetime
    since: datetime


@dataclass(frozen=True)
class LoginExpired:
    """Google refused the camera login; a person must log in again."""

    at: datetime


type Observation = Seen | NoPicture | VisitStarted | VisitEnded | CameraOffline | LoginExpired
