"""Communications handler "standard": the one gate every Announcement goes through.

For each Event it logs the kind and Urgency (never spoken). Log-only Events stop there.
Others are held back by, in order: the Pee announcements switch (Visit start guessing Pee),
Quiet Hours and Do Not Disturb (each lets only its `allow` Urgencies through), every
Listener being Away (Unknown does not hold back), no Message template, or the same text
said less than `repeat_seconds` ago. Then each Speaker for that Urgency says it, from its
own queue and thread (Urgent first), so the watcher never waits for a speaker. A text no
Speaker could say does not count as said; that is found on the watcher's thread, at the
next tick or Announcement, so only that thread touches what was said when.

When Quiet Hours end with Poop still in the Litter Box (a `poop` Event and no `poop_gone`
since), `poop_after_quiet_hours` is said once, through the same gate.
"""

import logging
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import Future
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from catpoop.communications.messages import message_text
from catpoop.communications.quiet_hours import active_quiet_hours
from catpoop.communications.speaker_queue import SpeakerQueue
from catpoop.communications.switches import Switches, Topic
from catpoop.config import Config, ConfigError, Household, QuietHours
from catpoop.domain import Event, Presence, Urgency
from catpoop.interfaces import PresenceCheck, Speaker
from catpoop.registry import COMMUNICATIONS, DEFAULT, PRESENCE, SPEAKER

log = logging.getLogger(__name__)

QUIET_TOPICS: dict[str, Topic] = {
    "poop": "poop",
    "poop_reminder": "poop",
    "poop_after_quiet_hours": "poop",
    "visit_started": "visits",
}


class CommunicationOptions(BaseModel):
    """The `[communications]` options."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dnd_allow: list[Urgency] = [Urgency.URGENT]
    """Urgencies Do Not Disturb lets through, unless `catpoop dnd --allow` says otherwise."""
    repeat_seconds: float = Field(30, ge=0)
    """The same text is not said again within this many seconds."""


@dataclass(frozen=True)
class RoutedSpeaker:
    """A Speaker and the Urgencies it says (`[[speakers]] urgencies`, default all)."""

    speaker: Speaker
    urgencies: frozenset[Urgency]


@dataclass(frozen=True)
class _Route:
    """A Speaker's queue and the Urgencies it says."""

    queue: SpeakerQueue
    urgencies: frozenset[Urgency]


@dataclass(frozen=True)
class _Saying:
    """A text handed to Speakers at `at`, and whether each one said it, when known."""

    text: str
    at: datetime
    said: tuple[Future[bool], ...]


class StandardCommunications:
    """Decides whether and where each Event is said (see the module docstring)."""

    def __init__(
        self,
        *,
        speakers: Sequence[RoutedSpeaker],
        presence: PresenceCheck,
        listeners: Sequence[str],
        quiet_hours: Sequence[QuietHours],
        zone: ZoneInfo,
        messages: Mapping[str, str],
        household: Household,
        switches: Switches,
        options: CommunicationOptions | None = None,
    ) -> None:
        """`zone` is the Litter Box's time zone, which Quiet Hours are read in."""
        self._routes = [_Route(SpeakerQueue(r.speaker), r.urgencies) for r in speakers]
        self._presence = presence
        self._listeners = list(listeners)
        self._quiet_hours = list(quiet_hours)
        self._zone = zone
        self._messages = dict(messages)
        self._household = household
        self._switches = switches
        self._options = options or CommunicationOptions()
        self._last_said: dict[str, datetime] = {}
        self._saying: list[_Saying] = []
        self._poop_in_box = False
        self._was_quiet: bool | None = None

    def resume_poop(self, since: datetime, now: datetime) -> None:
        """Poop found at `since` is still in the Litter Box, as the event log says at a restart.

        Quiet Hours are taken as of `since`, so Poop held back by them is said once they end.
        """
        self._poop_in_box = True
        self._was_quiet = bool(active_quiet_hours(self._quiet_hours, since, self._zone))

    def handle(self, event: Event) -> None:
        """Log `event` and announce it if it is not log only and the rules allow it."""
        if event.kind == "poop":
            self._poop_in_box = True
        elif event.kind == "poop_gone":
            self._poop_in_box = False
        if not event.announce:
            log.info("%s (%s) %s: log only", event.kind, event.urgency, event.details)
            return
        self._announce(event)

    def tick(self, at: datetime) -> None:
        """Say Poop once if Quiet Hours have just ended with Poop still in the Litter Box."""
        self._forget_unsaid()
        quiet = bool(active_quiet_hours(self._quiet_hours, at, self._zone))
        just_ended = self._was_quiet and not quiet
        self._was_quiet = quiet
        if just_ended and self._poop_in_box:
            self._announce(Event("poop_after_quiet_hours", Urgency.NORMAL, at))

    def _announce(self, event: Event) -> None:
        self._forget_unsaid()
        reason = self._held_back(event)
        text = None
        if reason is None:
            text = message_text(self._messages, self._household, event)
            if text is None:
                reason = "no message template"
            elif self._said_recently(text, event.at):
                reason = "said less than repeat_seconds ago"
        if reason or text is None:
            log.info("%s (%s) %s: not said, %s", event.kind, event.urgency, event.details, reason)
            return
        routed = [route.queue for route in self._routes if event.urgency in route.urgencies]
        if not routed:
            log.info("%s (%s) %s: no Speaker for it", event.kind, event.urgency, event.details)
            return
        self._last_said[text] = event.at
        said = tuple(queue.put(text, event.urgency) for queue in routed)
        self._saying.append(_Saying(text, event.at, said))
        log.info("%s (%s) %s: saying %r", event.kind, event.urgency, event.details, text)

    def close(self, seconds: float) -> bool:
        """Wait at most `seconds` in all for the Speakers to say what they were given.

        False if time ran out. Speaker threads end with the process, so a text still waiting
        then is lost.
        """
        end = time.monotonic() + seconds
        return all([route.queue.wait(max(0.0, end - time.monotonic())) for route in self._routes])

    def _forget_unsaid(self) -> None:
        """Texts that every Speaker failed to say no longer count as said."""
        still = []
        for saying in self._saying:
            if not all(future.done() for future in saying.said):
                still.append(saying)
            elif not any(future.result() for future in saying.said):
                if self._last_said.get(saying.text) == saying.at:
                    del self._last_said[saying.text]
                log.info("no Speaker could say %r", saying.text)
        self._saying = still

    def _held_back(self, event: Event) -> str | None:
        """Why `event` must not be said now, or None."""
        if (
            event.kind == "visit_started"
            and event.details.get("guess") == "pee"
            and not self._switches.pee_announcements()
        ):
            return "Pee announcements are off"
        topic = QUIET_TOPICS.get(event.kind)
        if topic and self._switches.quiet_until(topic, event.at):
            return f"{topic} switched to quiet"
        for period in active_quiet_hours(self._quiet_hours, event.at, self._zone):
            if event.urgency not in period.allow:
                return "Quiet Hours"
        dnd = self._switches.do_not_disturb(event.at)
        if dnd:
            allow = self._options.dnd_allow if dnd.allow is None else dnd.allow
            if event.urgency not in allow:
                return "Do Not Disturb"
        if self._listeners and all(
            self._presence.check(name) is Presence.AWAY for name in self._listeners
        ):
            return "every Listener is Away"
        return None

    def _said_recently(self, text: str, at: datetime) -> bool:
        last = self._last_said.get(text)
        return last is not None and at - last < timedelta(seconds=self._options.repeat_seconds)


def _routed(config: Config) -> list[RoutedSpeaker]:
    """One Speaker per `[[speakers]]` entry, with the Urgencies it says."""
    routed = []
    for settings in config.speakers:
        wanted = (settings.model_extra or {}).get("urgencies", list(Urgency))
        try:
            urgencies = frozenset(Urgency(value) for value in wanted)
        except (TypeError, ValueError):
            raise ConfigError(f"speakers {settings.name}: urgencies {wanted!r}") from None
        speaker = DEFAULT.create(SPEAKER, settings.kind, config, settings.model_dump())
        routed.append(RoutedSpeaker(speaker, urgencies))
    return routed


@DEFAULT.part(COMMUNICATIONS, "standard")
def _create(config: Config, options: Mapping[str, Any]) -> StandardCommunications:
    try:
        parsed = CommunicationOptions.model_validate(dict(options))
    except ValidationError as error:
        problems = "; ".join(f"communications.{e['loc'][0]}: {e['msg']}" for e in error.errors())
        raise ConfigError(problems) from None
    return StandardCommunications(
        speakers=_routed(config),
        presence=DEFAULT.create(PRESENCE, config.parts.presence, config, config.presence),
        listeners=[listener.name for listener in config.listeners],
        quiet_hours=config.quiet_hours,
        zone=ZoneInfo(config.outcome.timezone),
        messages=config.messages,
        household=config.household,
        switches=Switches.default(),
        options=parsed,
    )
