from catpoop.config import VisitSettings
from catpoop.domain import Detection
from catpoop.visits.finder import VisitSpan, cat_in_litter_box, find_visits

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
