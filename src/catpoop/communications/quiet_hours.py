"""Which Quiet Hours are on at a moment.

A period that ends before it starts runs overnight and belongs to the day it starts on.
"""

from collections.abc import Sequence
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from catpoop.config import QuietHours

_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def active_quiet_hours(
    periods: Sequence[QuietHours], at: datetime, zone: ZoneInfo
) -> list[QuietHours]:
    """The periods that are on at `at`, read in the Litter Box time zone `zone`."""
    return [period for period in periods if _is_on(period, at.astimezone(zone))]


def _is_on(period: QuietHours, local: datetime) -> bool:
    today = _DAYS[local.weekday()]
    yesterday = _DAYS[(local - timedelta(days=1)).weekday()]
    now = local.time().replace(tzinfo=None)
    if period.start < period.end:
        return today in period.days and period.start <= now < period.end
    return (today in period.days and now >= period.start) or (
        yesterday in period.days and now < period.end
    )
