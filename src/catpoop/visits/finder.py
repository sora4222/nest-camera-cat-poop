"""Find Visits in a clip: from the Cat going into the Litter Box until it comes out."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from catpoop.config import VisitSettings
from catpoop.domain import Detection


@dataclass(frozen=True)
class VisitSpan:
    """Where a Visit is in its clip, in seconds from the start (padding included)."""

    start: float
    end: float


def cat_in_litter_box(detections: Sequence[Detection], settings: VisitSettings) -> bool:
    """Whether a Cat was found with the middle of its box inside the Litter Box."""
    left, top, right, bottom = settings.litter_box
    for found in detections:
        if found.label != settings.cat_label:
            continue
        x = (found.box[0] + found.box[2]) / 2
        y = (found.box[1] + found.box[3]) / 2
        if left <= x <= right and top <= y <= bottom:
            return True
    return False


def find_visits(
    samples: Iterable[tuple[float, bool]], clip_end: float, settings: VisitSettings
) -> list[VisitSpan]:
    """Visits from `(seconds, cat seen)` samples in time order, in a clip `clip_end` long."""
    sightings: list[list[float]] = []
    for seconds, seen in samples:
        if not seen:
            continue
        if sightings and seconds - sightings[-1][1] <= settings.end_gap_seconds:
            sightings[-1][1] = seconds
        else:
            sightings.append([seconds, seconds])
    return [
        VisitSpan(
            max(0.0, first - settings.padding_seconds),
            min(clip_end, last + settings.padding_seconds),
        )
        for first, last in sightings
        if last - first >= settings.min_seconds
    ]
