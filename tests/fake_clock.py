"""A clock for tests: time only moves when something sleeps or the test moves it."""

from datetime import datetime, timedelta


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.time = start
        self.slept: list[float] = []

    def now(self) -> datetime:
        return self.time

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.advance(seconds)

    def advance(self, seconds: float) -> None:
        self.time += timedelta(seconds=seconds)
