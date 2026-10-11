"""The small interface to Google's Data Portability API that the `portability` importer uses."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol


class PortabilityError(Exception):
    """The Data Portability API refused or failed (it is not offered in every country)."""


@dataclass(frozen=True)
class ArchiveState:
    """An export job's state: `IN_PROGRESS`, `COMPLETE`, `FAILED` or `CANCELLED`."""

    state: str
    urls: list[str] = field(default_factory=list)
    """Signed download links, once `COMPLETE`. They expire."""


class PortabilityApi(Protocol):
    """Starts an export job, checks on it and downloads its archives."""

    def initiate(
        self, resources: Sequence[str], start: datetime | None, end: datetime | None
    ) -> str:
        """Start exporting `resources` and return the archive job id."""
        ...

    def state(self, job_id: str) -> ArchiveState:
        """The job's current state."""
        ...

    def download(self, url: str, to: Path) -> None:
        """Save the archive at `url` to the file `to`."""
        ...
