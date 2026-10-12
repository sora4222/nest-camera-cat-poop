"""Find Visits: from the Cat going into the Litter Box until it comes out.

`VisitTracker` follows sightings one sample at a time (the live watcher);
`find_visits` runs it over a whole clip.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from catpoop.config import VisitSettings
from catpoop.domain import Detection


@dataclass(frozen=True)
class VisitSpan:
    """Where a Visit is, in seconds (padding included)."""

    start: float
    end: float


@dataclass(frozen=True)
class VisitStarted:
    """The Cat has now stayed `min_seconds`; it was first seen at `first_seen`."""

    first_seen: float


@dataclass(frozen=True)
class VisitEnded:
    """The Cat has been gone `end_gap_seconds`; `span` is the padded Visit."""

    span: VisitSpan


type VisitChange = VisitStarted | VisitEnded


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


class VisitTracker:
    """Says when a Visit starts and ends, from `(seconds, cat seen)` samples in time order.

    Sightings less than `end_gap_seconds` apart belong to one Visit. A Visit starts once
    its sightings span `min_seconds`, and ends at the first sample `end_gap_seconds`
    after the last sighting.
    """

    def __init__(self, settings: VisitSettings) -> None:
        """Start with no Cat seen."""
        self._settings = settings
        self._sighting: tuple[float, float] | None = None
        self._started = False

    @property
    def in_visit(self) -> bool:
        """Whether a Visit has started and not ended."""
        return self._started

    def see(self, seconds: float, seen: bool) -> list[VisitChange]:
        """What changed with the sample at `seconds`."""
        changes: list[VisitChange] = []
        if self._sighting and seconds - self._sighting[1] > self._settings.end_gap_seconds:
            ended = self._close()
            if ended:
                changes.append(ended)
        if not seen:
            return changes
        first = self._sighting[0] if self._sighting else seconds
        self._sighting = (first, seconds)
        if not self._started and seconds - first >= self._settings.min_seconds:
            self._started = True
            changes.append(VisitStarted(first))
        return changes

    def finish(self) -> VisitEnded | None:
        """End the Visit going on, if any (the clip or the watch is over)."""
        return self._close()

    def _close(self) -> VisitEnded | None:
        sighting, started = self._sighting, self._started
        self._sighting, self._started = None, False
        if sighting is None or not started:
            return None
        pad = self._settings.padding_seconds
        return VisitEnded(VisitSpan(sighting[0] - pad, sighting[1] + pad))


def find_visits(
    samples: Iterable[tuple[float, bool]], clip_end: float, settings: VisitSettings
) -> list[VisitSpan]:
    """Visits from `(seconds, cat seen)` samples in time order, in a clip `clip_end` long."""
    tracker = VisitTracker(settings)
    ended = [c for s, seen in samples for c in tracker.see(s, seen) if isinstance(c, VisitEnded)]
    last = tracker.finish()
    if last:
        ended.append(last)
    return [VisitSpan(max(0.0, e.span.start), min(clip_end, e.span.end)) for e in ended]
