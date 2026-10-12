"""History importer `folder`: clips saved by hand from the Google Home app.

`paths` are folders; every MP4 inside them (at any depth) is imported.
"""

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from catpoop.config import Config
from catpoop.history.archive import archive_clips
from catpoop.history.importer import HistoryClip
from catpoop.history.options import paths_option
from catpoop.registry import DEFAULT, HISTORY_IMPORTER


class FolderImporter:
    """Reads every MP4 in the given folders."""

    def __init__(self, paths: list[Path]) -> None:
        """Read the folders at `paths`."""
        self.paths = paths

    def clips(self) -> Iterator[HistoryClip]:
        """Every clip in every folder, in order."""
        for path in self.paths:
            if not path.is_dir():
                raise ValueError(f"{path}: not a folder")
            yield from archive_clips(path, "folder")


@DEFAULT.part(HISTORY_IMPORTER, "folder")
def _create(config: Config, options: Mapping[str, Any]) -> FolderImporter:
    return FolderImporter(paths_option("folder", options))
