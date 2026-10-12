from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from catpoop.alexa_skill.spoken_time import spoken_time

ZONE = ZoneInfo("Australia/Melbourne")  # UTC+11 in October
NOW = datetime(2026, 10, 11, 3, 0, tzinfo=UTC)  # Sunday 2 PM there


def local(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=ZONE)


@pytest.mark.parametrize(
    ("at", "said"),
    [
        (local(11, 17, 30), "5:30 PM"),
        (local(11, 9), "9 AM"),
        (local(11, 0, 5), "12:05 AM"),
        (local(11, 12), "12 PM"),
        (local(12, 7), "tomorrow at 7 AM"),
        (local(10, 23, 15), "yesterday at 11:15 PM"),
        (local(14, 8), "Wednesday at 8 AM"),
        (local(7, 8), "Wednesday at 8 AM"),
        (local(25, 8), "October 25 at 8 AM"),
    ],
)
def test_times_are_said_in_the_litter_box_zone_relative_to_today(at, said):
    assert spoken_time(at, NOW, ZONE) == said
