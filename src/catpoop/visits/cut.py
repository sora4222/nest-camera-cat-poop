"""Cut every new history clip into Visits with the detector, and save their frames."""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from catpoop.config import VisitSettings
from catpoop.domain import Frame
from catpoop.interfaces import Detector
from catpoop.visits.finder import cat_in_litter_box, find_visits
from catpoop.visits.store import Visit, VisitStore, visit_id
from catpoop.visits.video import VideoError, read_frames

log = logging.getLogger(__name__)

_UNKNOWN_TIME = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class CutCounts:
    """How many clips were cut, how many Visits were found and how many clips failed."""

    clips: int
    visits: int
    failed: int


def recorded_at(clip: Path) -> str | None:
    """When `clip` was recorded, from the record beside it in the clip store."""
    record = clip.with_suffix(".json")
    if not record.exists():
        return None
    return json.loads(record.read_text()).get("recorded_at")


def cut_clip(
    clip: Path, detector: Detector, store: VisitStore, settings: VisitSettings
) -> list[Visit]:
    """Find the Visits in `clip` and save each new one with its frames."""
    sha = clip.stem
    when = recorded_at(clip)
    base = datetime.fromisoformat(when) if when else _UNKNOWN_TIME
    samples = []
    clip_end = 0.0
    for seconds, image in read_frames(clip, settings.frame_seconds):
        found = detector.detect(Frame(base + timedelta(seconds=seconds), image))
        samples.append((seconds, cat_in_litter_box(found, settings)))
        clip_end = seconds
    saved = []
    for span in find_visits(samples, clip_end, settings):
        visit = Visit(visit_id(sha, span.start), sha, span.start, span.end, when)
        if store.get(visit.id) is not None:
            continue  # already labeled; keep it as it is
        images = (
            image for _, image in read_frames(clip, settings.frame_seconds, span.start, span.end)
        )
        saved.append(store.add(visit, images))
    return saved


def cut_clips(private_data_store: Path, detector: Detector, settings: VisitSettings) -> CutCounts:
    """Cut every clip in `history/clips` that has not been cut yet."""
    store = VisitStore(private_data_store)
    clips = visits = failed = 0
    for clip in sorted((private_data_store / "history" / "clips").glob("*.mp4")):
        if store.is_scanned(clip.stem):
            continue
        try:
            found = cut_clip(clip, detector, store, settings)
        except VideoError as error:
            log.warning("cannot read %s: %s", clip.name, error)
            failed += 1
            continue
        store.mark_scanned(clip.stem)
        log.info("%s: %d Visits", clip.name, len(found))
        clips += 1
        visits += len(found)
    return CutCounts(clips, visits, failed)
