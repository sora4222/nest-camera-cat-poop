"""A past clip of the Litter Box, and the interface every history importer follows."""

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import IO, Any, Protocol


@dataclass(frozen=True)
class HistoryClip:
    """One original MP4 from the camera history and where it came from.

    `open` gives the clip's bytes. It is only valid until the importer yields the next clip.
    """

    source: str
    """Where it came from: an importer (`takeout`, `portability`, `folder`), `manual` or `live`."""
    origin: str
    """Where it was inside that source, such as `export.zip!Takeout/Nest/clip.mp4`."""
    name: str
    """The original file name."""
    open: Callable[[], IO[bytes]]
    recorded_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    """The sidecar JSON that came with the clip, if any, unchanged."""


class HistoryImporter(Protocol):
    """Finds past clips in one kind of source (an export, an API, a folder)."""

    def clips(self) -> Iterator[HistoryClip]:
        """Every clip in the source."""
        ...
