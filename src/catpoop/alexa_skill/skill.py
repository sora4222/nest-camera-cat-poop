"""What the skill says and does for each Alexa request (already verified).

It flips the same switches as `make dnd` and `make pee-on/off` (switches.json), and reads
the Litter Box status from the event log. Intent names match
`alexa/interactionModels/custom/en-US.json`.
"""

from collections.abc import Callable
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

from catpoop.alexa_skill.durations import parse_alexa_duration
from catpoop.alexa_skill.poop_status import litter_box_status
from catpoop.alexa_skill.spoken_time import spoken_time
from catpoop.clock import Clock
from catpoop.communications.switches import Switches
from catpoop.interfaces import EventLog

MAX_QUIET = timedelta(weeks=1)
_HELP = (
    "You can ask: is there poop in the box? Or say: be quiet for two hours, stop being quiet, "
    "or turn pee announcements on or off. What would you like?"
)
_REPROMPT = "What would you like? For example: is there poop in the box?"
_HOW_LONG = "For how long should I be quiet? For example: two hours."

type Answer = dict[str, Any]


def _say(text: str, *, listen: str | None = None) -> Answer:
    """A response that says `text`; with `listen`, the session stays open and reprompts."""
    response: dict[str, Any] = {
        "outputSpeech": {"type": "PlainText", "text": text},
        "shouldEndSession": listen is None,
    }
    if listen is not None:
        response["reprompt"] = {"outputSpeech": {"type": "PlainText", "text": listen}}
    return {"version": "1.0", "response": response}


class AlexaSkill:
    """Answers Alexa requests for Do Not Disturb, Pee announcements and status."""

    def __init__(
        self,
        switches: Switches,
        event_log: EventLog,
        clock: Clock,
        zone: ZoneInfo,
        cat: str = "the cat",
    ) -> None:
        """`zone` is the Litter Box's time zone, which times are said in."""
        self._switches = switches
        self._event_log = event_log
        self._clock = clock
        self._zone = zone
        self._cat = cat

    def answer(self, request: dict[str, Any]) -> Answer:
        """The response envelope for one Alexa request."""
        inner = request.get("request") or {}
        kind = inner.get("type")
        if kind == "LaunchRequest":
            return _say("Litter box here. " + _HELP, listen=_REPROMPT)
        if kind == "IntentRequest":
            intent = inner.get("intent") or {}
            handler = INTENTS.get(intent.get("name", ""), AlexaSkill._help)
            return handler(self, _slots(intent))
        return {"version": "1.0", "response": {}}  # SessionEndedRequest and the like

    def _do_not_disturb(self, slots: dict[str, str]) -> Answer:
        value = slots.get("duration")
        if not value:
            return _say(_HOW_LONG, listen=_HOW_LONG)
        try:
            span = parse_alexa_duration(value)
        except ValueError:
            return _say("Sorry, I didn't get how long. " + _HOW_LONG, listen=_HOW_LONG)
        if span > MAX_QUIET:
            return _say("I can be quiet for up to a week. " + _HOW_LONG, listen=_HOW_LONG)
        now = self._clock.now()
        self._switches.set_do_not_disturb(now + span)
        return _say(f"OK, I'll be quiet until {spoken_time(now + span, now, self._zone)}.")

    def _stop_do_not_disturb(self, slots: dict[str, str]) -> Answer:
        was_on = self._switches.do_not_disturb(self._clock.now()) is not None
        self._switches.clear_do_not_disturb()
        return _say("OK, Do Not Disturb is off." if was_on else "Do Not Disturb was not on.")

    def _pee_on(self, slots: dict[str, str]) -> Answer:
        self._switches.set_pee_announcements(True)
        return _say("OK, I'll announce pee again.")

    def _pee_off(self, slots: dict[str, str]) -> Answer:
        self._switches.set_pee_announcements(False)
        return _say("OK, I won't announce pee.")

    def _status(self, slots: dict[str, str]) -> Answer:
        now = self._clock.now()
        status = litter_box_status(self._event_log)
        if status.poop_since is not None:
            when = spoken_time(status.poop_since, now, self._zone)
            parts = [f"Yes, there has been poop in the litter box since {when}."]
        else:
            parts = ["No, there is no poop in the litter box."]
            if status.last_visit is not None:
                when = spoken_time(status.last_visit, now, self._zone)
                parts.append(f"{self._cat[:1].upper()}{self._cat[1:]} last visited at {when}.")
        dnd = self._switches.do_not_disturb(now)
        if dnd is not None:
            parts.append(f"Do Not Disturb is on until {spoken_time(dnd.until, now, self._zone)}.")
        if not self._switches.pee_announcements():
            parts.append("Pee announcements are off.")
        return _say(" ".join(parts))

    def _help(self, slots: dict[str, str]) -> Answer:
        return _say(_HELP, listen=_REPROMPT)

    def _goodbye(self, slots: dict[str, str]) -> Answer:
        return _say("Bye.")


INTENTS: dict[str, Callable[[AlexaSkill, dict[str, str]], Answer]] = {
    "DoNotDisturbIntent": AlexaSkill._do_not_disturb,
    "DurationIntent": AlexaSkill._do_not_disturb,  # a bare "two hours" after "how long?"
    "StopDoNotDisturbIntent": AlexaSkill._stop_do_not_disturb,
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
