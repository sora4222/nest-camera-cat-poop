import logging
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fake_clock import FakeClock

from catpoop.communications.switches import Switches
from catpoop.config import Config, ConfigError, Household, QuietHours, load_config
from catpoop.domain import Event, Presence, Urgency
from catpoop.parts.standard_communications import (
    CommunicationOptions,
    RoutedSpeaker,
    StandardCommunications,
)
from catpoop.registry import COMMUNICATIONS, default_registry

START = datetime(2026, 6, 1, 20, 0, tzinfo=UTC)  # a Monday
NIGHTS = QuietHours(
    days=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
    start=time(22),
    end=time(7),
    allow=[Urgency.URGENT],
)
MESSAGES = {
    "visit_started": "{cat} is in the box.",
    "poop": "{cat} left poop.",
    "poop_reminder": "Poop is still there.",
    "dog_at_poop": "{dog} is at the poop.",
    "poop_after_quiet_hours": "There is poop from the night.",
}


class FakeSpeaker:
    def __init__(self, name: str, fails: bool = False) -> None:
        self.name = name
        self.said: list[str] = []
        self.fails = fails

    def say(self, text: str) -> None:
        if self.fails:
            raise ConnectionError("speaker unplugged")
        self.said.append(text)


class FakePresence:
    def __init__(self, presence: Presence = Presence.UNKNOWN) -> None:
        self.presence = presence

    def check(self, listener: str) -> Presence:
        return self.presence


class Setup:
    """A handler with one Speaker for every Urgency, at the fake clock's time."""

    def __init__(self, tmp_path, quiet=(), presence=None, speakers=None, **options) -> None:
        self.clock = FakeClock(START)
        self.speaker = FakeSpeaker("Living room")
        self.switches = Switches(tmp_path / "switches.json")
        self.presence = presence or FakePresence()
        self.handler = StandardCommunications(
            speakers=speakers or [RoutedSpeaker(self.speaker, frozenset(Urgency))],
            presence=self.presence,
            listeners=["Partner"],
            quiet_hours=list(quiet),
            zone=ZoneInfo("UTC"),
            messages=MESSAGES,
            household=Household(cat="Cat", dog="Dog"),
            switches=self.switches,
            options=CommunicationOptions(**options),
        )

    def event(self, kind, urgency=Urgency.NORMAL, announce=True, **details) -> None:
        self.handler.handle(Event(kind, urgency, self.clock.now(), details, announce))

    def wait(self, seconds: float, every: float = 60) -> None:
        """Move the clock on, ticking the handler like the watcher does."""
        end = self.clock.now() + timedelta(seconds=seconds)
        while self.clock.now() < end:
            self.clock.advance(every)
            self.handler.tick(self.clock.now())


def test_an_event_is_said_on_every_speaker_from_its_message_template(tmp_path):
    first, second = FakeSpeaker("Living room"), FakeSpeaker("Kitchen")
    setup = Setup(
        tmp_path,
        speakers=[
            RoutedSpeaker(first, frozenset(Urgency)),
            RoutedSpeaker(second, frozenset(Urgency)),
        ],
    )
    setup.event("poop")
    assert first.said == second.said == ["Cat left poop."]


def test_urgency_is_logged_but_never_spoken(tmp_path, caplog):
    setup = Setup(tmp_path)
    with caplog.at_level(logging.INFO):
        setup.event("dog_at_poop", Urgency.URGENT)
    assert setup.speaker.said == ["Dog is at the poop."]
    assert "urgent" in caplog.text


def test_log_only_events_are_logged_and_not_said(tmp_path, caplog):
    setup = Setup(tmp_path)
    with caplog.at_level(logging.INFO):
        setup.event("visit_ended", Urgency.INFO, announce=False)
        setup.event("visit_started", Urgency.INFO, announce=False)
    assert setup.speaker.said == []
    assert "visit_ended" in caplog.text


def test_an_event_with_no_message_template_is_not_said(tmp_path):
    setup = Setup(tmp_path)
    setup.event("camera_offline")
    assert setup.speaker.said == []


def test_speakers_only_say_the_urgencies_they_are_for(tmp_path):
    bedroom = FakeSpeaker("Bedroom")
    hall = FakeSpeaker("Hall")
    setup = Setup(
        tmp_path,
        speakers=[
            RoutedSpeaker(bedroom, frozenset({Urgency.URGENT})),
            RoutedSpeaker(hall, frozenset(Urgency)),
        ],
    )
    setup.event("poop")
    setup.event("dog_at_poop", Urgency.URGENT)
    assert bedroom.said == ["Dog is at the poop."]
    assert hall.said == ["Cat left poop.", "Dog is at the poop."]


def test_a_broken_speaker_does_not_stop_the_others(tmp_path, caplog):
    broken, working = FakeSpeaker("Broken", fails=True), FakeSpeaker("Working")
    setup = Setup(
        tmp_path,
        speakers=[
            RoutedSpeaker(broken, frozenset(Urgency)),
            RoutedSpeaker(working, frozenset(Urgency)),
        ],
    )
    setup.event("poop")
    assert working.said == ["Cat left poop."]
    assert "Broken" in caplog.text


def test_quiet_hours_hold_back_urgencies_they_do_not_allow(tmp_path):
    setup = Setup(tmp_path, quiet=[NIGHTS])
    setup.clock.advance(3 * 3600)  # 23:00
    setup.event("poop")
    setup.event("dog_at_poop", Urgency.URGENT)
    assert setup.speaker.said == ["Dog is at the poop."]


def test_do_not_disturb_holds_back_all_but_the_configured_urgencies(tmp_path):
    setup = Setup(tmp_path)
    setup.switches.set_do_not_disturb(START + timedelta(hours=2))
    setup.event("poop")
    setup.event("dog_at_poop", Urgency.URGENT)
    assert setup.speaker.said == ["Dog is at the poop."]
    setup.clock.advance(2 * 3600)
    setup.event("poop_reminder")
    assert setup.speaker.said[-1] == "Poop is still there."


def test_do_not_disturb_can_hold_back_everything(tmp_path):
    setup = Setup(tmp_path)
    setup.switches.set_do_not_disturb(START + timedelta(hours=2), allow=[])
    setup.event("dog_at_poop", Urgency.URGENT)
    assert setup.speaker.said == []


def test_default_dnd_allow_comes_from_the_options(tmp_path):
    setup = Setup(tmp_path, dnd_allow=[Urgency.NORMAL, Urgency.URGENT])
    setup.switches.set_do_not_disturb(START + timedelta(hours=2))
    setup.event("poop")
    setup.event("visit_started", Urgency.INFO)
    assert setup.speaker.said == ["Cat left poop."]


def test_pee_announcements_switch_holds_back_pee_guesses_only(tmp_path):
    setup = Setup(tmp_path)
    setup.switches.set_pee_announcements(False)
    setup.event("visit_started", Urgency.INFO, guess="pee")
    setup.event("visit_started", Urgency.INFO, guess="poop")
    assert setup.speaker.said == ["Cat is in the box."]
    setup.switches.set_pee_announcements(True)
    setup.clock.advance(3600)
    setup.event("visit_started", Urgency.INFO, guess="pee")
    assert len(setup.speaker.said) == 2


def test_nothing_is_said_while_every_listener_is_away(tmp_path):
    setup = Setup(tmp_path, presence=FakePresence(Presence.AWAY))
    setup.event("dog_at_poop", Urgency.URGENT)
    assert setup.speaker.said == []
    setup.presence.presence = Presence.UNKNOWN  # the check is off or broken: still said
    setup.event("poop")
    assert setup.speaker.said == ["Cat left poop."]


def test_the_same_text_is_not_said_again_within_repeat_seconds(tmp_path):
    setup = Setup(tmp_path, repeat_seconds=30)
    setup.event("poop")
    setup.clock.advance(29)
    setup.event("poop")
    setup.clock.advance(1)
    setup.event("poop")
    assert setup.speaker.said == ["Cat left poop.", "Cat left poop."]


def test_poop_still_in_the_box_at_the_end_of_quiet_hours_is_said_once(tmp_path):
    setup = Setup(tmp_path, quiet=[NIGHTS])
    setup.clock.advance(3 * 3600)  # 23:00, quiet
    setup.event("poop")
    setup.wait(9 * 3600)  # to 08:00, Quiet Hours end at 07:00
    assert setup.speaker.said == ["There is poop from the night."]


def test_no_poop_said_at_the_end_of_quiet_hours_once_it_is_gone(tmp_path):
    setup = Setup(tmp_path, quiet=[NIGHTS])
    setup.clock.advance(3 * 3600)
    setup.event("poop")
    setup.event("poop_gone", Urgency.INFO, announce=False)
    setup.wait(9 * 3600)
    assert setup.speaker.said == []


def test_no_poop_said_at_the_end_of_quiet_hours_with_no_poop(tmp_path):
    setup = Setup(tmp_path, quiet=[NIGHTS])
    setup.clock.advance(3 * 3600)
    setup.wait(9 * 3600)
    assert setup.speaker.said == []


def test_poop_after_quiet_hours_still_respects_do_not_disturb(tmp_path):
    setup = Setup(tmp_path, quiet=[NIGHTS])
    setup.clock.advance(3 * 3600)
    setup.event("poop")
    setup.switches.set_do_not_disturb(START + timedelta(hours=14))
    setup.wait(9 * 3600)
    assert setup.speaker.said == []


def test_standard_communications_are_built_from_the_example_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    config = load_config(Path(__file__).parents[1] / "config.example.toml")
    handler = default_registry().create(
        COMMUNICATIONS, config.parts.communications, config, config.communications
    )
    assert isinstance(handler, StandardCommunications)


def test_wrong_options_and_speaker_urgencies_are_config_errors(tmp_path):
    def config(speaker: dict) -> Config:
        return Config.model_validate(
            {
                "parts": {
                    "camera": "nest",
                    "detector": "onnx",
                    "event_rules": "standard",
                    "event_log": "memory",
                    "presence": "off",
                    "communications": "standard",
                },
                "paths": {"private_data_store": str(tmp_path)},
                "speakers": [{"name": "Hall", "kind": "log", **speaker}],
            }
        )

    registry = default_registry()
    with pytest.raises(ConfigError, match="repeat_secs"):
        registry.create(COMMUNICATIONS, "standard", config({}), {"repeat_secs": 1})
    with pytest.raises(ConfigError, match="loud"):
        registry.create(COMMUNICATIONS, "standard", config({"urgencies": ["loud"]}), {})
    built = registry.create(COMMUNICATIONS, "standard", config({"urgencies": ["urgent"]}), {})
    assert isinstance(built, StandardCommunications)
