"""Event rules "standard": Visits, Poop and its Reminders, Dog at Poop, camera problems.

- Visit start: announced with the Outcome Guess (Pee guesses only if `announce_pee`).
- Visit end: logged with the Outcome; a wrong Outcome Guess is only logged. Poop is announced
  and starts the Poop Reminders. The first reminder is always spoken; later ones only if a
  Listener is Home (Unknown counts as Away).
- Poop is gone once a person was at the Litter Box and then the surface no longer scores Poop.
- Dog at Poop: Urgent, once per approach.
- Camera Offline and Login Expired are said; Login Expired again once at
  `timers.login_expired_reminder_at` (Litter Box time) if still broken.
"""

import logging
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, ValidationError

from catpoop import observations as obs
from catpoop.config import Config, ConfigError, Timers, VisitSettings
from catpoop.domain import Event, Outcome, Presence, Urgency
from catpoop.interfaces import PresenceCheck
from catpoop.poop_reminders import PoopReminders
from catpoop.registry import DEFAULT, EVENT_RULES, PRESENCE
from catpoop.visits.finder import labels_in_litter_box

log = logging.getLogger(__name__)


class RuleOptions(BaseModel):
    """The `[event_rules]` options."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    announce_pee: bool = True
    """Announce Visits whose Outcome Guess is Pee."""
    dog_label: str = "dog"
    person_label: str = "person"
    dog_gone_seconds: float = 60
    """The Dog must be away from the Litter Box this long before Dog at Poop is said again."""


class StandardEventRules:
    """Turns what the live watcher sees into Events (see the module docstring)."""

    def __init__(
        self,
        *,
        timers: Timers,
        visits: VisitSettings,
        presence: PresenceCheck,
        listeners: Sequence[str],
        zone: ZoneInfo,
        options: RuleOptions | None = None,
    ) -> None:
        """`zone` is the Litter Box's time zone, for the Login Expired reminder time."""
        self._timers = timers
        self._visits = visits
        self._presence = presence
        self._listeners = list(listeners)
        self._zone = zone
        self._options = options or RuleOptions()
        self._reminders = PoopReminders(
            timers.poop_reminder_first_minutes,
            timers.poop_reminder_max_minutes,
            timers.poop_reminder_max_count,
        )
        self._guess: Outcome | None = None
        self._poop_in_box = False
        self._person_was_there = False
        self._dog_said_at: datetime | None = None
        self._login_reminder_at: datetime | None = None

    def update(self, observation: obs.Observation) -> list[Event]:
        """New Events now that the watcher has seen `observation`."""
        match observation:
            case obs.Seen():
                events = self._seen(observation)
            case obs.VisitStarted():
                events = [self._visit_started(observation)]
            case obs.VisitEnded():
                events = self._visit_ended(observation)
            case obs.CameraOffline(at=at, since=since):
                events = [Event("camera_offline", Urgency.NORMAL, at, {"since": since.isoformat()})]
            case obs.LoginExpired(at=at):
                self._login_reminder_at = self._next_reminder_time(at)
                events = [Event("login_expired", Urgency.NORMAL, at)]
            case _:
                events = []
        events += self._timed(observation.at)
        for event in events:
            log.info("%s %s", event.kind, event.details)
        return events

    def _visit_started(self, started: obs.VisitStarted) -> Event:
        self._guess = started.guess.best if started.guess else None
        if self._guess is None:
            return Event("visit_started", Urgency.INFO, started.at)
        announce = self._guess is not Outcome.PEE or self._options.announce_pee
        return Event(
            "visit_started", Urgency.INFO, started.at, {"guess": self._guess.value}, announce
        )

    def _visit_ended(self, ended: obs.VisitEnded) -> list[Event]:
        guess, self._guess = self._guess, None
        outcome = ended.outcome.best if ended.outcome else None
        details: dict[str, str] = {}
        if outcome:
            details["outcome"] = outcome.value
        if guess:
            details["guess"] = guess.value
        if outcome and guess:
            details["guess_right"] = "yes" if guess is outcome else "no"
            if guess is not outcome:
                log.info("Outcome Guess was wrong: guessed %s, was %s", guess, outcome)
        if ended.saved_visit:
            details["visit"] = ended.saved_visit
        events = [Event("visit_ended", Urgency.INFO, ended.at, details, announce=False)]
        if outcome is Outcome.POOP:
            self._poop_in_box = True
            self._person_was_there = False
            self._reminders.start(ended.at)
            events.append(Event("poop", Urgency.NORMAL, ended.at))
        return events

    def _seen(self, seen: obs.Seen) -> list[Event]:
        self._login_reminder_at = None
        if not self._poop_in_box:
            return []
        inside = labels_in_litter_box(seen.detections, self._visits)
        events = self._dog(seen.at, self._options.dog_label in inside)
        if self._options.person_label in inside:
            self._person_was_there = True
        elif seen.surface and self._person_was_there:
            if seen.surface.best is Outcome.POOP:
                self._person_was_there = False
            else:
                self._poop_in_box = False
                self._reminders.stop()
                events.append(Event("poop_gone", Urgency.INFO, seen.at, announce=False))
        return events

    def _dog(self, at: datetime, dog_in_box: bool) -> list[Event]:
        """Dog at Poop the first time the Dog is at the box, again only after it left a while."""
        if dog_in_box:
            first = self._dog_said_at is None
            self._dog_said_at = at
            return [Event("dog_at_poop", Urgency.URGENT, at)] if first else []
        gone = timedelta(seconds=self._options.dog_gone_seconds)
        if self._dog_said_at and at - self._dog_said_at >= gone:
            self._dog_said_at = None
        return []

    def _timed(self, at: datetime) -> list[Event]:
        """Poop Reminders and the Login Expired reminder that are due at `at`."""
        events = []
        number = self._reminders.due(at)
        if number:
            announce = number == 1 or self._someone_home()
            details = {"number": str(number)}
            events.append(Event("poop_reminder", Urgency.NORMAL, at, details, announce))
        if self._login_reminder_at and at >= self._login_reminder_at:
            self._login_reminder_at = None
            events.append(Event("login_expired", Urgency.NORMAL, at, {"reminder": "yes"}))
        return events

    def _someone_home(self) -> bool:
        return any(self._presence.check(name) is Presence.HOME for name in self._listeners)

    def _next_reminder_time(self, at: datetime) -> datetime:
        """The first `login_expired_reminder_at` (Litter Box time) after `at`."""
        local = at.astimezone(self._zone)
        reminder = datetime.combine(
            local.date(), self._timers.login_expired_reminder_at, self._zone
        )
        return reminder if reminder > local else reminder + timedelta(days=1)


@DEFAULT.part(EVENT_RULES, "standard")
def _create(config: Config, options: Mapping[str, Any]) -> StandardEventRules:
    try:
        rule_options = RuleOptions.model_validate(dict(options))
    except ValidationError as error:
        problems = "; ".join(f"event_rules.{e['loc'][0]}: {e['msg']}" for e in error.errors())
        raise ConfigError(problems) from None
    presence = DEFAULT.create(PRESENCE, config.parts.presence, config, config.presence)
    return StandardEventRules(
        timers=config.timers,
        visits=config.visits,
        presence=presence,
        listeners=[listener.name for listener in config.listeners],
        zone=ZoneInfo(config.outcome.timezone),
        options=rule_options,
    )
