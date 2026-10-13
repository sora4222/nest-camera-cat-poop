"""Keep the Private Data Store under its size limit by deleting the oldest unlabeled clips.

A clip with a labeled Visit is never deleted. Unlabeled Visits of a deleted clip go with it.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from catpoop.visits.store import Visit, VisitStore

log = logging.getLogger(__name__)


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


def _still_unlabeled(store: VisitStore, listed: list[Visit]) -> list[Visit] | None:
    """Re-read `listed` from disk; None if one was labeled since (`make label` runs apart)."""
    current = [visit for visit in (store.get(v.id) for v in listed) if visit is not None]
    if any(visit.outcome is not None for visit in current):
        return None
    return current


def prune_clips(private_data_store: Path, max_bytes: int) -> list[str]:
    """Delete the oldest clips with no labeled Visit while the store is over `max_bytes`.

    Returns the hashes of the deleted clips, oldest first.
    """
    size = store_size(private_data_store)
    if size <= max_bytes:
        return []
    store = VisitStore(private_data_store)
    visits = store.all()
    keep = {v.clip for v in visits if v.outcome is not None}
    unlabeled: dict[str, list[Visit]] = {}
    for visit in visits:
        if visit.outcome is None:
            unlabeled.setdefault(visit.clip, []).append(visit)
    clips = [
        clip
        for clip in (private_data_store / "history" / "clips").glob("*.mp4")
        if clip.stem not in keep
    ]
    removed = []
    for clip in sorted(clips, key=_age_key):
        if size <= max_bytes:
            break
        sha = clip.stem
        still_unlabeled = _still_unlabeled(store, unlabeled.get(sha, []))
        if still_unlabeled is None:
            continue
        size -= store.remove_unlabeled(sha, still_unlabeled)
        for path in (clip, clip.with_suffix(".json")):
            if path.exists():
                size -= path.stat().st_size
                path.unlink()
        log.info("deleted unlabeled clip %s", clip.name)
        removed.append(sha)
    return removed
