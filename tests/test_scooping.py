from datetime import UTC, datetime, timedelta

from catpoop.domain import Outcome
from catpoop.scooping import Scooping

AT = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)


def later(seconds: float) -> datetime:
    return AT + timedelta(seconds=seconds)


def test_no_poop_scored_is_not_gone_until_a_person_was_at_the_box():
    scoop = Scooping(settle_seconds=120)
    assert not scoop.surface_seen(AT, Outcome.NOTHING)
    scoop.person_at_box(later(1))
    assert scoop.surface_seen(later(2), Outcome.NOTHING)


def test_poop_scored_within_the_settle_window_is_ignored():
    scoop = Scooping(settle_seconds=120)
    scoop.person_at_box(AT)
    assert not scoop.surface_seen(later(119), Outcome.POOP)
    assert scoop.surface_seen(later(130), Outcome.NOTHING)


def test_poop_scored_after_the_settle_window_needs_a_person_again():
    scoop = Scooping(settle_seconds=120)
    scoop.person_at_box(AT)
    assert not scoop.surface_seen(later(120), Outcome.POOP)
    assert not scoop.surface_seen(later(121), Outcome.NOTHING)


def test_the_window_counts_from_the_last_time_the_person_was_seen():
    scoop = Scooping(settle_seconds=120)
    scoop.person_at_box(AT)
    scoop.person_at_box(later(100))
    assert not scoop.surface_seen(later(200), Outcome.POOP)
    assert scoop.surface_seen(later(201), Outcome.NOTHING)


def test_reset_forgets_the_person():
    scoop = Scooping(settle_seconds=120)
    scoop.person_at_box(AT)
    scoop.reset()
    assert not scoop.surface_seen(later(1), Outcome.NOTHING)
