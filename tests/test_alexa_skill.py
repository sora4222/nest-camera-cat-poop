from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fake_clock import FakeClock

from catpoop.alexa_skill.skill import INTENTS, AlexaSkill
from catpoop.communications.switches import Switches
from catpoop.domain import Event, Urgency
from catpoop.parts.memory_event_log import MemoryEventLog

NOW = datetime(2026, 10, 11, 14, 0, tzinfo=UTC)


@pytest.fixture
def parts(tmp_path):
    switches = Switches(tmp_path / "switches.json")
    event_log = MemoryEventLog()
    clock = FakeClock(NOW)
    skill = AlexaSkill(switches, event_log, clock, ZoneInfo("UTC"), cat="Whiskers")
    return skill, switches, event_log, clock


def intent(name: str, **slots: str) -> dict:
    return {
        "version": "1.0",
        "request": {
            "type": "IntentRequest",
            "intent": {
                "name": name,
                "slots": {key: {"name": key, "value": value} for key, value in slots.items()},
            },
        },
    }


def speech(answer: dict) -> str:
    return answer["response"]["outputSpeech"]["text"]


def ends(answer: dict) -> bool:
    return answer["response"]["shouldEndSession"]


def test_launch_says_what_it_can_do_and_listens(parts):
    skill, *_ = parts
    answer = skill.respond({"request": {"type": "LaunchRequest"}})
    assert answer["version"] == "1.0"
    assert "poop" in speech(answer).lower()
    assert not ends(answer)
    assert answer["response"]["reprompt"]["outputSpeech"]["text"]


def test_do_not_disturb_for_a_while(parts):
    skill, switches, _, _ = parts
    answer = skill.respond(intent("DoNotDisturbIntent", duration="PT2H"))
    dnd = switches.do_not_disturb(NOW)
    assert dnd is not None
    assert dnd.until == NOW + timedelta(hours=2)
    assert dnd.allow is None  # the [communications] dnd_allow default, as `make dnd`
    assert speech(answer) == "OK, I'll be quiet until 4 PM."
    assert ends(answer)


def test_do_not_disturb_with_no_duration_asks_how_long(parts):
    skill, switches, _, _ = parts
    answer = skill.respond(intent("DoNotDisturbIntent"))
    assert "how long" in speech(answer).lower()
    assert not ends(answer)
    assert switches.do_not_disturb(NOW) is None


@pytest.mark.parametrize("value", ["?", "P1M", "nonsense"])
def test_do_not_disturb_with_a_duration_it_cannot_use_asks_again(parts, value):
    skill, switches, _, _ = parts
    answer = skill.respond(intent("DoNotDisturbIntent", duration=value))
    assert not ends(answer)
    assert switches.do_not_disturb(NOW) is None


def test_do_not_disturb_is_at_most_a_week(parts):
    skill, switches, _, _ = parts
    answer = skill.respond(intent("DoNotDisturbIntent", duration="P8D"))
    assert "week" in speech(answer)
    assert switches.do_not_disturb(NOW) is None


def test_stop_do_not_disturb(parts):
    skill, switches, _, _ = parts
    switches.set_do_not_disturb(NOW + timedelta(hours=1))
    answer = skill.respond(intent("StopDoNotDisturbIntent"))
    assert switches.do_not_disturb(NOW) is None
    assert speech(answer) == "OK, Do Not Disturb is off."


def test_stop_do_not_disturb_when_it_was_not_on(parts):
    skill, *_ = parts
    assert speech(skill.respond(intent("StopDoNotDisturbIntent"))) == "Do Not Disturb was not on."


def test_pee_announcements_off_and_on(parts):
    skill, switches, _, _ = parts
    off = skill.respond(intent("PeeAnnouncementsOffIntent"))
    assert switches.pee_announcements() is False
    assert speech(off) == "OK, I won't announce pee."
    on = skill.respond(intent("PeeAnnouncementsOnIntent"))
    assert switches.pee_announcements() is True
    assert speech(on) == "OK, I'll announce pee again."


def test_status_with_poop_in_the_box(parts):
    skill, _, event_log, _ = parts
    event_log.record(Event("visit_ended", Urgency.INFO, NOW - timedelta(minutes=20)))
    event_log.record(Event("poop", Urgency.NORMAL, NOW - timedelta(minutes=20)))
    answer = skill.respond(intent("StatusIntent"))
    assert speech(answer) == "Yes, there has been poop in the litter box since 1:40 PM."
    assert ends(answer)


def test_status_with_a_clean_box(parts):
    skill, _, event_log, _ = parts
    event_log.record(Event("poop", Urgency.NORMAL, NOW - timedelta(hours=3)))
    event_log.record(Event("poop_gone", Urgency.INFO, NOW - timedelta(hours=2)))
    event_log.record(Event("visit_ended", Urgency.INFO, NOW - timedelta(hours=1)))
    answer = skill.respond(intent("StatusIntent"))
    assert (
        speech(answer) == "No, there is no poop in the litter box. Whiskers last visited at 1 PM."
    )


def test_status_with_nothing_in_the_log(parts):
    skill, *_ = parts
    assert (
        speech(skill.respond(intent("StatusIntent"))) == "No, there is no poop in the litter box."
    )


def test_status_mentions_do_not_disturb_and_pee_announcements_off(parts):
    skill, switches, _, _ = parts
    switches.set_do_not_disturb(NOW + timedelta(minutes=30))
    switches.set_pee_announcements(False)
    said = speech(skill.respond(intent("StatusIntent")))
    assert "Do Not Disturb is on until 2:30 PM." in said
    assert "Pee announcements are off." in said


@pytest.mark.parametrize("name", ["AMAZON.HelpIntent", "AMAZON.FallbackIntent", "SomethingElse"])
def test_help_fallback_and_unknown_intents_say_what_it_can_do_and_listen(parts, name):
    skill, *_ = parts
    answer = skill.respond(intent(name))
    assert "poop" in speech(answer).lower()
    assert not ends(answer)


@pytest.mark.parametrize("name", ["AMAZON.StopIntent", "AMAZON.CancelIntent"])
def test_stop_and_cancel_end_the_session(parts, name):
    skill, *_ = parts
    assert ends(skill.respond(intent(name)))


def test_session_ended_gets_an_empty_response(parts):
    skill, *_ = parts
    answer = skill.respond({"request": {"type": "SessionEndedRequest", "reason": "USER_INITIATED"}})
    assert answer == {"version": "1.0", "response": {}}


def test_the_intents_it_knows(parts):
    assert set(INTENTS) >= {
        "DoNotDisturbIntent",
        "StopDoNotDisturbIntent",
        "PeeAnnouncementsOnIntent",
        "PeeAnnouncementsOffIntent",
        "StatusIntent",
        "AMAZON.HelpIntent",
        "AMAZON.StopIntent",
        "AMAZON.CancelIntent",
        "AMAZON.FallbackIntent",
    }
