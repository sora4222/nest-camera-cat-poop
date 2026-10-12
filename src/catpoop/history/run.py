"""Copy every clip an importer finds into the history clip store."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from catpoop.history.clip_store import HistoryClipStore
from catpoop.history.importer import HistoryImporter

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImportCounts:
    """How many clips were new and how many were already stored."""

    new: int
    known: int


def import_history(
    importer: HistoryImporter,
    store: HistoryClipStore,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> ImportCounts:
    """Save every clip from `importer` into `store`."""
    new = known = 0
    for clip in importer.clips():
        saved = store.save(clip, now())
        log.info("%s %s -> %s", "new" if saved.new else "known", clip.origin, saved.path.name)
        if saved.new:
            new += 1
        else:
            known += 1
    return ImportCounts(new, known)
