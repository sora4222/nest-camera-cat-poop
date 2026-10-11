"""Event log kept in memory; lost on restart. For tests and trying things out."""

from collections.abc import Mapping
from typing import Any

from catpoop.config import Config
from catpoop.domain import Event
from catpoop.registry import DEFAULT, EVENT_LOG


class MemoryEventLog:
    """Keeps Events in a list."""

    def __init__(self) -> None:
        """Start empty."""
        self._events: list[Event] = []

    def record(self, event: Event) -> None:
        """Store `event`."""
        self._events.append(event)

    def recent(self, limit: int) -> list[Event]:
        """Up to `limit` Events, newest first."""
        return self._events[::-1][:limit]


@DEFAULT.part(EVENT_LOG, "memory")
def _create(config: Config, options: Mapping[str, Any]) -> MemoryEventLog:
    return MemoryEventLog()
