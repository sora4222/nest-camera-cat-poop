"""Event rules "log": pass Visits and camera problems straight through as Events and log them.

A stand-in until the real event rules: no Poop Reminders, no Dog at Poop.
"""

import logging
from collections.abc import Mapping
from typing import Any

from catpoop import observations as obs
from catpoop.config import Config
from catpoop.domain import Event, Urgency
from catpoop.registry import DEFAULT, EVENT_RULES

log = logging.getLogger(__name__)


class LogEventRules:
    """One Event per Visit start, Visit end, Camera Offline and Login Expired."""

    def update(self, observation: obs.Observation) -> list[Event]:
        """The Event for `observation`, if it is one that matters."""
        match observation:
            case obs.VisitStarted(at=at, guess=guess):
                details = {"guess": guess.best.value} if guess else {}
                event = Event("visit_started", Urgency.INFO, at, details)
            case obs.VisitEnded(at=at, outcome=outcome, saved_visit=saved):
                details = {"outcome": outcome.best.value} if outcome else {}
                if saved:
                    details["visit"] = saved
                event = Event("visit_ended", Urgency.INFO, at, details)
            case obs.CameraOffline(at=at):
                event = Event("camera_offline", Urgency.NORMAL, at)
            case obs.LoginExpired(at=at):
                event = Event("login_expired", Urgency.NORMAL, at)
            case _:
                return []
        log.info("%s %s", event.kind, event.details)
        return [event]


@DEFAULT.part(EVENT_RULES, "log")
def _create(config: Config, options: Mapping[str, Any]) -> LogEventRules:
    return LogEventRules()
