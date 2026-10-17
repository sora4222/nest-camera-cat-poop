"""Find Visits: from the Cat going into the Litter Box until it comes out.

`VisitTracker` follows sightings one sample at a time (the live watcher);
`find_visits` runs it over a whole clip.
"""

from collections.abc import Callable, Iterable, Sequence
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


type Box = tuple[float, float, float, float]
"""Left, top, right, bottom as fractions of the Frame size."""


def _middle_inside(box: Box, area: Box) -> bool:
    """Whether the middle of `box` is inside `area` (its edges count as inside)."""
    left, top, right, bottom = box
    x, y = (left + right) / 2, (top + bottom) / 2
    return area[0] <= x <= area[2] and area[1] <= y <= area[3]


def _overlaps(box: Box, area: Box) -> bool:
    """Whether `box` and `area` share some space (only touching edges does not count)."""
    left, top, right, bottom = box
    return min(right, area[2]) > max(left, area[0]) and min(bottom, area[3]) > max(top, area[1])


def _labels_where(
    detections: Sequence[Detection], settings: VisitSettings, test: Callable[[Box, Box], bool]
) -> set[str]:
    return {found.label for found in detections if test(found.box, settings.litter_box)}


def labels_in_litter_box(detections: Sequence[Detection], settings: VisitSettings) -> set[str]:
    """Labels of everything found with the middle of its box inside the Litter Box."""
    return _labels_where(detections, settings, _middle_inside)


def labels_over_litter_box(detections: Sequence[Detection], settings: VisitSettings) -> set[str]:
    """Labels of everything found whose box overlaps the Litter Box (reaching into it)."""
    return _labels_where(detections, settings, _overlaps)


def cat_in_litter_box(detections: Sequence[Detection], settings: VisitSettings) -> bool:
    """Whether a Cat was found with the middle of its box inside the Litter Box."""
    return settings.cat_label in labels_in_litter_box(detections, settings)


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
