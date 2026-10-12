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
    """When the Poop still in the box was seen; None if there is none (or none known)."""
    last_visit: datetime | None
    """When the last Visit ended, if one is in the log."""


def litter_box_status(event_log: EventLog, look_back: int = LOOK_BACK) -> LitterBoxStatus:
    """The status from the newest `look_back` Events."""
    poop_since: datetime | None = None
    poop_known = False
    last_visit: datetime | None = None
    for event in event_log.recent(look_back):  # newest first
        if not poop_known and event.kind in ("poop", "poop_gone"):
            poop_known = True
            poop_since = event.at if event.kind == "poop" else None
        if last_visit is None and event.kind == "visit_ended":
            last_visit = event.at
        if poop_known and last_visit is not None:
            break
    return LitterBoxStatus(poop_since, last_visit)
