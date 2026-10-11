"""Small interfaces for the swappable parts. Implementations are chosen in config.

Each part is registered by name in `catpoop.registry`. Tests use fakes, never real
cameras, speakers or the network.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from catpoop.domain import Detection, Event, Frame, Presence


class CameraSource(Protocol):
    """Gives pictures of the Litter Box."""

    def read(self) -> Frame | None:
        """The next Frame, or None if there is no picture right now."""
        ...


class Detector(Protocol):
    """Finds the Cat, Dog and people in a Frame."""

    def detect(self, frame: Frame) -> list[Detection]:
        """Everything found in `frame`."""
        ...


class EventRules(Protocol):
    """Turns what the camera sees over time into Events."""

    def update(self, now: datetime, detections: Sequence[Detection] | None) -> list[Event]:
        """New Events at `now`. `detections` is None when there was no picture."""
        ...


class EventLog(Protocol):
    """Keeps every Event."""

    def record(self, event: Event) -> None:
        """Store `event`."""
        ...

    def recent(self, limit: int) -> list[Event]:
        """Up to `limit` Events, newest first."""
        ...


class PresenceCheck(Protocol):
    """Says whether a Listener is home."""

    def check(self, listener: str) -> Presence:
        """Presence of the Listener named `listener` in config."""
        ...


class Speaker(Protocol):
    """A device that says a message out loud."""

    name: str

    def say(self, text: str) -> None:
        """Say `text` now."""
        ...


class CommunicationsHandler(Protocol):
    """The one gate every Announcement goes through (Quiet Hours, presence, Speakers)."""

    def handle(self, event: Event) -> None:
        """Announce `event` if the rules allow it."""
        ...
