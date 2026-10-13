"""Add a short clip found by hand straight to the dataset as one labeled Visit."""

from datetime import datetime
from pathlib import Path

from catpoop.config import VisitSettings
from catpoop.domain import Outcome
from catpoop.history.clip_store import HistoryClipStore
from catpoop.history.importer import HistoryClip
from catpoop.visits.cut import recorded_at
from catpoop.visits.store import Visit, VisitStore, visit_id
from catpoop.visits.video import VideoError, clip_seconds, read_frames


def add_visit(
    clip: Path, outcome: Outcome, private_data_store: Path, settings: VisitSettings, now: datetime
) -> Visit:
    """Store `clip` with the history clips and save all of it as a Visit with `outcome`."""
    length = clip_seconds(clip)
    if not sum(1 for _ in read_frames(clip, settings.frame_seconds)):
        raise VideoError(f"{clip}: no video frames")
    saved = HistoryClipStore(private_data_store).save(
        HistoryClip("manual", clip.name, clip.name, lambda: clip.open("rb")), now
    )
    store = VisitStore(private_data_store)
    visit = Visit(
        visit_id(saved.sha256, 0),
        saved.sha256,
        0.0,
        length,
        recorded_at(saved.path),
        source="manual",
        outcome=outcome,
        labeled_at=now.isoformat(),
    )
    images = (image for _, image in read_frames(saved.path, settings.frame_seconds))
    added = store.add(visit, images)
    store.mark_scanned(saved.sha256)
    return added
