"""Is there Poop in the Litter Box? Read from the newest Events in the event log.

Poop is in the box after a `poop` Event until a `poop_gone` Event, as the communications
handler counts it.
"""

from dataclasses import dataclass
from datetime import datetime

from catpoop.interfaces import EventLog

LOOK_BACK = 2000
"""Events read back; older Poop than this (days of Visits and reminders) is not known."""


@dataclass(frozen=True)
class LitterBoxStatus:
    """What the event log says about the Litter Box now."""

    poop_since: datetime | None
    """When the Poop still in the box was first seen (the first `poop` since the last
    `poop_gone`); None if there is none (or none known)."""
    last_visit: datetime | None
    """When the last Visit ended, if one is in the log."""
    newest_poop: datetime | None = None
    """When Poop was last found while still in the box (Poop Reminders count from it)."""


def litter_box_status(event_log: EventLog, look_back: int = LOOK_BACK) -> LitterBoxStatus:
    """The status from the newest `look_back` Events."""
    poop_since: datetime | None = None
    newest_poop: datetime | None = None
    gone_found = False
    last_visit: datetime | None = None
    for event in event_log.recent(look_back):  # newest first
        if not gone_found and event.kind == "poop":
            poop_since = event.at
            newest_poop = newest_poop or event.at
        elif event.kind == "poop_gone":
            gone_found = True
        if last_visit is None and event.kind == "visit_ended":
            last_visit = event.at
        if gone_found and last_visit is not None:
            break
    return LitterBoxStatus(poop_since, last_visit, newest_poop)
