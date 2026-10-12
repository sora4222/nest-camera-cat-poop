"""History importer `takeout`: clips from a Google Takeout export of Google Nest data.

`paths` are the export's archive parts (`.zip`/`.tgz`) or the folder they were unpacked to.
"""

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from catpoop.config import Config
from catpoop.history.archive import archive_clips
from catpoop.history.importer import HistoryClip
from catpoop.history.options import paths_option
from catpoop.registry import DEFAULT, HISTORY_IMPORTER


class TakeoutImporter:
    """Reads every MP4 in the given Takeout archive parts."""

    def __init__(self, paths: list[Path]) -> None:
        """Read the archives or folders at `paths`."""
        self.paths = paths

    def clips(self) -> Iterator[HistoryClip]:
        """Every clip in every part, in order."""
        for path in self.paths:
            yield from archive_clips(path, "takeout")


@DEFAULT.part(HISTORY_IMPORTER, "takeout")
def _create(config: Config, options: Mapping[str, Any]) -> TakeoutImporter:
    return TakeoutImporter(paths_option("takeout", options))
