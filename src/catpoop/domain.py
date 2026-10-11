"""Shared words from GLOSSARY.md as types, passed between the swappable parts."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class Urgency(StrEnum):
    """How important an Announcement is. Never spoken aloud."""

    INFO = "info"
    NORMAL = "normal"
    URGENT = "urgent"


class Presence(StrEnum):
    """Whether a Listener is at home. Unknown counts as Away."""

    HOME = "home"
    AWAY = "away"
    UNKNOWN = "unknown"


class Outcome(StrEnum):
    """What a Visit left behind."""

    PEE = "pee"
    POOP = "poop"
    NOTHING = "nothing"


@dataclass(frozen=True)
class Frame:
    """One picture from the camera. `image` is whatever the camera source gives (an array)."""

    taken_at: datetime
    image: Any


@dataclass(frozen=True)
class Detection:
    """Something the detector found in a Frame, such as `cat`, `dog` or `person`."""

    label: str
    score: float
    box: tuple[float, float, float, float]
    """Left, top, right, bottom as fractions of the Frame size."""


@dataclass(frozen=True)
class Event:
    """Something worth logging and maybe announcing, such as a Visit starting."""

    kind: str
    urgency: Urgency
    at: datetime
    details: dict[str, str] = field(default_factory=dict)
