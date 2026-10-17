"""Keep the Private Data Store under its size limit by deleting the oldest unlabeled clips.

A clip with a labeled Visit is never deleted. Unlabeled Visits of a deleted clip go with it.
"""

import json
import logging
from contextlib import AbstractContextManager, nullcontext
from datetime import UTC, datetime
from pathlib import Path

from catpoop.visits.store import VisitStore

log = logging.getLogger(__name__)

_NO_LOCK = nullcontext()
"""For a prune with nothing else writing to the store (`catpoop cut-visits`)."""


def store_size(root: Path) -> int:
    """Bytes in every file under `root`."""
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _age_key(clip: Path) -> str:
    """When `clip` was recorded, else when its file was written, as sortable text."""
    record = clip.with_suffix(".json")
    if record.exists():
        when = json.loads(record.read_text()).get("recorded_at")
        if when:
            return datetime.fromisoformat(when).astimezone(UTC).isoformat()
    return datetime.fromtimestamp(clip.stat().st_mtime, UTC).isoformat()


def prune_clips(
    private_data_store: Path, max_bytes: int, lock: AbstractContextManager[object] = _NO_LOCK
) -> list[str]:
    """Delete the oldest clips with no labeled Visit while the store is over `max_bytes`.

    Each clip's check and delete hold `lock`, so a save that holds it too waits for at most
    one clip. Returns the hashes of the deleted clips, oldest first.
    """
    size = store_size(private_data_store)
    if size <= max_bytes:
        return []
    store = VisitStore(private_data_store)
    clips = (private_data_store / "history" / "clips").glob("*.mp4")
    removed = []
    for clip in sorted(clips, key=_age_key):
        if size <= max_bytes:
            break
        sha = clip.stem
        with lock:
            if any(visit.outcome is not None for visit in store.visits_of(sha)):
                continue  # read just now: `make label` runs apart and may have labeled one
            size -= store.remove_unlabeled(sha)
            for path in (clip, clip.with_suffix(".json")):
                if path.exists():
                    size -= path.stat().st_size
                    path.unlink()
        log.info("deleted unlabeled clip %s", clip.name)
        removed.append(sha)
    return removed
