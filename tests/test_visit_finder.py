from catpoop.config import VisitSettings
from catpoop.domain import Detection
from catpoop.visits.finder import (
    VisitEnded,
    VisitSpan,
    VisitTracker,
    cat_in_litter_box,
    find_visits,
    labels_in_litter_box,
)

SETTINGS = VisitSettings(end_gap_seconds=3, min_seconds=2, padding_seconds=1)


def samples(seen: str, step: float = 1.0) -> list[tuple[float, bool]]:
    """One sample per character: `C` is the Cat in the Litter Box, `.` is not."""
    return [(i * step, c == "C") for i, c in enumerate(seen)]


def test_no_cat_no_visit():
    assert find_visits(samples("......"), 6, SETTINGS) == []


def test_visit_runs_from_first_to_last_sight_with_padding():
    assert find_visits(samples("...CCCC....."), 12, SETTINGS) == [VisitSpan(2, 7)]


def test_short_gaps_do_not_end_a_visit():
    assert find_visits(samples("..CC..CC......"), 14, SETTINGS) == [VisitSpan(1, 8)]


def test_long_gaps_split_visits():
    assert find_visits(samples("CCC.....CCC..."), 14, SETTINGS) == [
        VisitSpan(0, 3),
        VisitSpan(7, 11),
    ]


def test_short_visits_are_dropped():
    assert find_visits(samples("....C......"), 11, SETTINGS) == []


def test_padding_stays_inside_the_clip():
    assert find_visits(samples("CCCCC"), 4.5, SETTINGS) == [VisitSpan(0, 4.5)]


def cat(box, label="cat"):
    return Detection(label, 0.9, box)


def test_cat_counts_only_inside_the_litter_box():
    settings = VisitSettings(litter_box=(0.5, 0.5, 1.0, 1.0))
    assert cat_in_litter_box([cat((0.6, 0.6, 0.8, 0.8))], settings)
    assert not cat_in_litter_box([cat((0.0, 0.0, 0.3, 0.3))], settings)
    assert not cat_in_litter_box([cat((0.6, 0.6, 0.8, 0.8), "dog")], settings)


def test_labels_in_litter_box_lists_whatever_is_inside():
    settings = VisitSettings(litter_box=(0.5, 0.5, 1.0, 1.0))
    found = [cat((0.6, 0.6, 0.8, 0.8), "dog"), cat((0.0, 0.0, 0.3, 0.3), "person")]
    assert labels_in_litter_box(found, settings) == {"dog"}


def changes(seen: str) -> list[tuple[float, str]]:
    """Feed one sample per character to a VisitTracker; list what it said and when."""
    tracker = VisitTracker(SETTINGS)
    said: list[tuple[float, str]] = []
    for seconds, cat_seen in samples(seen):
        for change in tracker.see(seconds, cat_seen):
            said.append((seconds, "end" if isinstance(change, VisitEnded) else "start"))
    return said


def test_tracker_starts_a_visit_once_the_cat_has_stayed_min_seconds():
    assert changes("..CCCC") == [(4, "start")]


def test_tracker_ends_a_visit_after_end_gap_seconds_without_the_cat():
    assert changes("CCC..CC.....") == [(2, "start"), (10, "end")]


def test_tracker_ignores_short_sightings():
    assert changes("C.......C......") == []


def test_tracker_gives_the_padded_span_when_a_visit_ends():
    tracker = VisitTracker(SETTINGS)
    ended = [c for s, seen in samples("..CCC.....") for c in tracker.see(s, seen)][-1]
    assert ended == VisitEnded(VisitSpan(1, 5))


def test_tracker_finish_closes_an_open_visit():
    tracker = VisitTracker(SETTINGS)
    for s, seen in samples("CCCC"):
        tracker.see(s, seen)
    assert tracker.in_visit
    assert tracker.finish() == VisitEnded(VisitSpan(-1, 4))
    assert not tracker.in_visit
