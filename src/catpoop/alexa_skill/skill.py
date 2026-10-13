"""What the skill says and does for each Alexa request (already verified).

It flips the quiet switches for Poop and for Visits and the same Pee switch as
`make pee-on/off` (switches.json), and reads the Litter Box status from the event log.
Intent names match `alexa/interactionModels/custom/en-US.json`.
"""

from collections.abc import Callable
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

from catpoop.alexa_skill.durations import parse_alexa_duration
from catpoop.alexa_skill.poop_status import litter_box_status
from catpoop.alexa_skill.spoken_time import spoken_time
from catpoop.clock import Clock
from catpoop.communications.switches import Switches, Topic
from catpoop.interfaces import EventLog

MAX_QUIET = timedelta(weeks=1)
_HELP = (
    "You can ask: is there poop in the box? Or say: no poop news for two hours, "
    "no pee news for an hour, or turn pee announcements on or off. What would you like?"
)
_REPROMPT = "What would you like? For example: is there poop in the box?"
_ABOUT: dict[Topic, str] = {"poop": "poop", "visits": "visits or pee"}
_QUIET_INTENTS: dict[str, Topic] = {"QuietPoopIntent": "poop", "QuietVisitsIntent": "visits"}

type Answer = dict[str, Any]


def _alexa_announce(text: str, *, listen: str | None = None, quiet: Topic | None = None) -> Answer:
    """A response that says `text`; with `listen`, the session stays open and reprompts.

    `quiet` is remembered in the session, so a bare "two hours" next knows what it is for.
    """
    response: dict[str, Any] = {
        "outputSpeech": {"type": "PlainText", "text": text},
        "shouldEndSession": listen is None,
    }
    if listen is not None:
        response["reprompt"] = {"outputSpeech": {"type": "PlainText", "text": listen}}
    answer: Answer = {"version": "1.0", "response": response}
    if quiet is not None:
        answer["sessionAttributes"] = {"quiet": quiet}
    return answer


def _no_news(topic: Topic) -> str:
    return "no poop news" if topic == "poop" else "no news about visits or pee"


def _how_long(topic: Topic) -> str:
    return f"For how long should I give {_no_news(topic)}? For example: two hours."


class AlexaSkill:
    """Answers Alexa requests for Do Not Disturb, Pee announcements and status."""

    def __init__(
        self,
        switches: Switches,
        event_log: EventLog,
        clock: Clock,
        timezone: ZoneInfo,
        cat: str = "the cat",
    ) -> None:
        """`timezone` is the Litter Box's time zone, which times are said in."""
        self._switches = switches
        self._event_log = event_log
        self._clock = clock
        self._timezone = timezone
        self._cat = cat

    def respond(self, request: dict[str, Any]) -> Answer:
        """The response envelope for one Alexa request."""
        inner = request.get("request") or {}
        kind = inner.get("type")
        if kind == "LaunchRequest":
            return _alexa_announce("Litter box here. " + _HELP, listen=_REPROMPT)
        if kind == "IntentRequest":
            intent = inner.get("intent") or {}
            name = intent.get("name", "")
            if name == "DurationIntent":  # the answer to "for how long?"
                attributes = (request.get("session") or {}).get("attributes") or {}
                topic = attributes.get("quiet")
                name = next((n for n, t in _QUIET_INTENTS.items() if t == topic), "")
            handler = INTENTS.get(name, AlexaSkill._help)
            return handler(self, _slots(intent))
        return {"version": "1.0", "response": {}}  # SessionEndedRequest and the like

    def _quiet(self, topic: Topic, slots: dict[str, str]) -> Answer:
        how_long = _how_long(topic)
        value = slots.get("duration")
        if not value:
            return _alexa_announce(how_long, listen=how_long, quiet=topic)
        try:
            span = parse_alexa_duration(value)
        except ValueError:
            again = "Sorry, I didn't get how long. " + how_long
            return _alexa_announce(again, listen=how_long, quiet=topic)
        if span > MAX_QUIET:
            again = "I can be quiet for up to a week. " + how_long
            return _alexa_announce(again, listen=how_long, quiet=topic)
        now = self._clock.now()
        self._switches.set_quiet(topic, now + span)
        until = spoken_time(now + span, now, self._timezone)
        return _alexa_announce(f"OK, {_no_news(topic)} until {until}.")

    def _quiet_poop(self, slots: dict[str, str]) -> Answer:
        return self._quiet("poop", slots)

    def _quiet_visits(self, slots: dict[str, str]) -> Answer:
        return self._quiet("visits", slots)

    def _stop_quiet(self, topic: Topic) -> Answer:
        was_on = self._switches.quiet_until(topic, self._clock.now()) is not None
        self._switches.clear_quiet(topic)
        if was_on:
            return _alexa_announce(f"OK, I'll tell you about {_ABOUT[topic]} again.")
        return _alexa_announce(f"I wasn't being quiet about {_ABOUT[topic]}.")

    def _stop_quiet_poop(self, slots: dict[str, str]) -> Answer:
        return self._stop_quiet("poop")

    def _stop_quiet_visits(self, slots: dict[str, str]) -> Answer:
        return self._stop_quiet("visits")

    def _pee_on(self, slots: dict[str, str]) -> Answer:
        self._switches.set_pee_announcements(True)
        return _alexa_announce("OK, I'll announce pee again.")

    def _pee_off(self, slots: dict[str, str]) -> Answer:
        self._switches.set_pee_announcements(False)
        return _alexa_announce("OK, I won't announce pee.")

    def _status(self, slots: dict[str, str]) -> Answer:
        now = self._clock.now()
        status = litter_box_status(self._event_log)
        if status.poop_since is not None:
            when = spoken_time(status.poop_since, now, self._timezone)
            parts = [f"Yes, there has been poop in the litter box since {when}."]
        else:
            parts = ["No, there is no poop in the litter box."]
            if status.last_visit is not None:
                when = spoken_time(status.last_visit, now, self._timezone)
                parts.append(f"{self._cat[:1].upper()}{self._cat[1:]} last visited at {when}.")
        dnd = self._switches.do_not_disturb(now)
        if dnd is not None:
            parts.append(
                f"Do Not Disturb is on until {spoken_time(dnd.until, now, self._timezone)}."
            )
        for topic in _ABOUT:
            until = self._switches.quiet_until(topic, now)
            if until is not None:
                no_news = _no_news(topic)
                when = spoken_time(until, now, self._timezone)
                parts.append(f"{no_news[:1].upper()}{no_news[1:]} until {when}.")
        if not self._switches.pee_announcements():
            parts.append("Pee announcements are off.")
        return _alexa_announce(" ".join(parts))

    def _help(self, slots: dict[str, str]) -> Answer:
        return _alexa_announce(_HELP, listen=_REPROMPT)

    def _goodbye(self, slots: dict[str, str]) -> Answer:
        return _alexa_announce("Bye.")


INTENTS: dict[str, Callable[[AlexaSkill, dict[str, str]], Answer]] = {
    "QuietPoopIntent": AlexaSkill._quiet_poop,
    "QuietVisitsIntent": AlexaSkill._quiet_visits,
    "DurationIntent": AlexaSkill._help,  # unless it answers "for how long?" (see `respond`)
    "StopQuietPoopIntent": AlexaSkill._stop_quiet_poop,
    "StopQuietVisitsIntent": AlexaSkill._stop_quiet_visits,
    "PeeAnnouncementsOnIntent": AlexaSkill._pee_on,
    "PeeAnnouncementsOffIntent": AlexaSkill._pee_off,
    "StatusIntent": AlexaSkill._status,
    "AMAZON.HelpIntent": AlexaSkill._help,
    "AMAZON.FallbackIntent": AlexaSkill._help,
    "AMAZON.NavigateHomeIntent": AlexaSkill._help,
    "AMAZON.StopIntent": AlexaSkill._goodbye,
    "AMAZON.CancelIntent": AlexaSkill._goodbye,
}
"""Intent name -> handler. Any other intent gets the help answer."""


def _slots(intent: dict[str, Any]) -> dict[str, str]:
    """Slot name -> value, for slots that have a value."""
    slots = intent.get("slots") or {}
    return {
        name: slot["value"]
        for name, slot in slots.items()
        if isinstance(slot, dict) and isinstance(slot.get("value"), str)
    }
