"""Small interfaces for the swappable parts. Implementations are chosen in config.

Each part is registered by name in `catpoop.registry`. Tests use fakes, never real
cameras, speakers or the network.
"""

from typing import Protocol

from catpoop.domain import Detection, Event, Frame, OutcomeScores, Presence
from catpoop.observations import Observation


class CameraLoginExpired(Exception):
    """The camera service refused the login; a person must log in again."""


class CameraSource(Protocol):
    """Gives pictures of the Litter Box."""

    def read(self) -> Frame | None:
        """The next new Frame, or None if there is no new picture right now.

        Raises `CameraLoginExpired` while the camera cannot be reached without a new login.
        """
        ...


class Detector(Protocol):
    """Finds the Cat, Dog and people in a Frame."""

    def detect(self, frame: Frame) -> list[Detection]:
        """Everything found in `frame`."""
        ...


class OutcomeModel(Protocol):
    """Decides the Outcome of a Visit and makes the Outcome Guess while it goes on."""

    def outcome(self, surface: Frame) -> OutcomeScores:
        """The Outcome, from a Frame of the litter surface after the Cat has left."""
        ...

    def guess(self, stance: Frame) -> OutcomeScores:
        """The Outcome Guess, from a Frame of the Cat in the Litter Box and its time of day."""
        ...


class EventRules(Protocol):
    """Turns what the live watcher sees over time into Events."""

    def update(self, observation: Observation) -> list[Event]:
        """New Events now that the watcher has seen `observation`."""
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
