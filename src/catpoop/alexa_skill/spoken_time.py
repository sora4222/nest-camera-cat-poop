"""A time as Alexa should say it: `5:30 PM`, `tomorrow at 7 AM`, `Wednesday at 8 AM`."""

from datetime import datetime
from zoneinfo import ZoneInfo


def spoken_time(at: datetime, now: datetime, zone: ZoneInfo) -> str:
    """`at` in `zone`, with the day said only when it is not today."""
    local, today = at.astimezone(zone), now.astimezone(zone).date()
    clock = f"{local.hour % 12 or 12}{f':{local.minute:02d}' if local.minute else ''}"
    clock += " AM" if local.hour < 12 else " PM"
    days = (local.date() - today).days
    if days == 0:
        return clock
    if days == 1:
        return f"tomorrow at {clock}"
    if days == -1:
        return f"yesterday at {clock}"
    if abs(days) < 7:
        return f"{local:%A} at {clock}"
    return f"{local:%B} {local.day} at {clock}"
