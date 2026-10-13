from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from catpoop.communications.quiet_hours import active_quiet_hours
from catpoop.config import QuietHours
from catpoop.domain import Urgency

WEEKNIGHTS = QuietHours(
    days=["sun", "mon", "tue", "wed", "thu"], start=time(22), end=time(7), allow=[Urgency.URGENT]
)
LUNCH = QuietHours(days=["sat"], start=time(12), end=time(13))
UTC_ZONE = ZoneInfo("UTC")


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """2026-06-01 is a Monday."""
    return datetime(2026, 6, day, hour, minute, tzinfo=UTC)


def test_an_overnight_period_runs_from_its_day_into_the_next_morning():
    assert active_quiet_hours([WEEKNIGHTS], at(1, 22), UTC_ZONE) == [WEEKNIGHTS]
    assert active_quiet_hours([WEEKNIGHTS], at(2, 6, 59), UTC_ZONE) == [WEEKNIGHTS]
    assert active_quiet_hours([WEEKNIGHTS], at(2, 7), UTC_ZONE) == []
    assert active_quiet_hours([WEEKNIGHTS], at(1, 21, 59), UTC_ZONE) == []


def test_an_overnight_period_belongs_to_the_day_it_starts():
    # Friday night is not listed, so Friday 23:00 and Saturday 06:00 are not quiet.
    assert active_quiet_hours([WEEKNIGHTS], at(5, 23), UTC_ZONE) == []
    assert active_quiet_hours([WEEKNIGHTS], at(6, 6), UTC_ZONE) == []
    # Sunday night runs into Monday morning.
    assert active_quiet_hours([WEEKNIGHTS], at(1, 6), UTC_ZONE) == [WEEKNIGHTS]


def test_a_daytime_period_and_many_periods():
    assert active_quiet_hours([WEEKNIGHTS, LUNCH], at(6, 12, 30), UTC_ZONE) == [LUNCH]
    assert active_quiet_hours([WEEKNIGHTS, LUNCH], at(6, 13), UTC_ZONE) == []


def test_quiet_hours_are_read_in_the_litter_box_time_zone():
    melbourne = ZoneInfo("Australia/Melbourne")  # UTC+10 in June
    assert active_quiet_hours([WEEKNIGHTS], at(1, 12), melbourne) == [WEEKNIGHTS]
    assert active_quiet_hours([WEEKNIGHTS], at(1, 22), melbourne) == []
