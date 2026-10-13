"""The time now and waiting, behind an interface so tests can use a fake clock."""

import time
from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Tells the time and waits."""

    def now(self) -> datetime:
        """The time now, with a time zone."""
        ...

    def sleep(self, seconds: float) -> None:
        """Wait `seconds`."""
        ...


class SystemClock:
    """The machine's clock, in UTC."""

    def now(self) -> datetime:
        """The time now in UTC."""
        return datetime.now(UTC)

    def sleep(self, seconds: float) -> None:
        """Wait `seconds`."""
        time.sleep(seconds)
