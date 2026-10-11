import logging
from datetime import UTC, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fake_clock import FakeClock

from catpoop import observations as obs
from catpoop.config import Config, ConfigError, Timers, VisitSettings, load_config
from catpoop.domain import Detection, Event, Frame, Outcome, OutcomeScores, Presence, Urgency
from catpoop.parts.sqlite_event_log import SqliteEventLog
from catpoop.parts.standard_event_rules import RuleOptions, StandardEventRules
from catpoop.registry import EVENT_LOG, EVENT_RULES, default_registry

START = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)
VISITS = VisitSettings(litter_box=(0.5, 0.5, 1.0, 1.0))
IN_BOX, OUTSIDE = (0.6, 0.6, 0.8, 0.8), (0.0, 0.0, 0.2, 0.2)


def scores(best: Outcome) -> OutcomeScores:
    return OutcomeScores({o: 1.0 if o is best else 0.0 for o in Outcome})


class FakePresence:
    def __init__(self, presence: Presence = Presence.UNKNOWN) -> None:
        self.presence = presence
        self.asked: list[str] = []

    def check(self, listener: str) -> Presence:
        self.asked.append(listener)
        return self.presence


class Feed:
    """Hands observations to the rules at the fake clock's time; keeps the Events."""

    def __init__(self, presence=None, timers=None, zone="UTC", **options) -> None:
        self.clock = FakeClock(START)
        self.presence = presence or FakePresence()
        self.rules = StandardEventRules(
            timers=timers or Timers(),
            visits=VISITS,
            presence=self.presence,
            listeners=["Partner"],
            zone=ZoneInfo(zone),
            options=RuleOptions(**options),
        )
        self.events: list[Event] = []

    def tell(self, observation: obs.Observation) -> list[Event]:
        new = self.rules.update(observation)
        self.events += new
        return new

    def seen(self, *labels: str, surface: Outcome | None = None, where=IN_BOX) -> list[Event]:
        found = tuple(Detection(label, 0.9, where) for label in labels)
        frame = Frame(self.clock.now(), None)
        return self.tell(
            obs.Seen(self.clock.now(), frame, found, scores(surface) if surface else None)
        )

    def visit(self, guess: Outcome | None, outcome: Outcome | None) -> list[Event]:
        started_at = self.clock.now()
        new = self.tell(obs.VisitStarted(started_at, (), scores(guess) if guess else None))
        self.clock.advance(60)
        ended = obs.VisitEnded(
            self.clock.now(), started_at, (), scores(outcome) if outcome else None, "v1"
        )
        return new + self.tell(ended)

    def wait(self, minutes: float, every: float = 30) -> list[Event]:
        """No picture every `every` seconds for `minutes`."""
        new: list[Event] = []
        for _ in range(int(minutes * 60 / every)):
            self.clock.advance(every)
            new += self.tell(obs.NoPicture(self.clock.now()))
        return new

    def kinds(self, events: list[Event] | None = None) -> list[str]:
        return [e.kind for e in (self.events if events is None else events)]


def test_pictures_with_nothing_going_on_make_no_events():
    feed = Feed()
    assert feed.seen("cat") == []
    assert feed.wait(5) == []


def test_visit_start_is_announced_with_the_outcome_guess():
    feed = Feed()
    [event] = feed.tell(obs.VisitStarted(START, (), scores(Outcome.PEE)))
    assert event == Event("visit_started", Urgency.INFO, START, {"guess": "pee"})


def test_pee_announcements_can_be_switched_off():
    feed = Feed(announce_pee=False)
    [pee] = feed.tell(obs.VisitStarted(START, (), scores(Outcome.PEE)))
    [poop] = feed.tell(obs.VisitStarted(START, (), scores(Outcome.POOP)))
    assert (pee.announce, poop.announce) == (False, True)


def test_visit_start_without_an_outcome_model_has_no_guess():
    [event] = Feed().tell(obs.VisitStarted(START, (), None))
    assert (event.details, event.announce) == ({}, True)


def test_a_visit_ending_is_only_logged_and_a_wrong_guess_noted(caplog):
    feed = Feed()
    with caplog.at_level(logging.INFO):
        _, ended = feed.visit(Outcome.POOP, Outcome.PEE)
    assert ended.kind == "visit_ended"
    assert not ended.announce
    assert ended.details == {"outcome": "pee", "guess": "poop", "guess_right": "no", "visit": "v1"}
    assert "wrong" in caplog.text


def test_poop_is_announced_when_the_visit_ends():
    feed = Feed()
    new = feed.visit(Outcome.POOP, Outcome.POOP)
    assert feed.kinds(new) == ["visit_started", "visit_ended", "poop"]
    assert (new[-1].urgency, new[-1].announce) == (Urgency.NORMAL, True)
    assert new[1].details["guess_right"] == "yes"


def test_poop_reminders_follow_the_schedule_and_only_the_first_is_spoken_when_away():
    feed = Feed(presence=FakePresence(Presence.UNKNOWN))
    feed.visit(None, Outcome.POOP)
    reminders = feed.wait(120)
    assert [r.details["number"] for r in reminders] == ["1", "2", "3", "4", "5", "6"]
    assert [round((r.at - START).total_seconds() / 60) for r in reminders] == [2, 3, 5, 9, 17, 33]
    assert [r.announce for r in reminders] == [True] + [False] * 5
    assert {r.kind for r in reminders} == {"poop_reminder"}


def test_repeat_reminders_are_spoken_when_a_listener_is_home():
    presence = FakePresence(Presence.HOME)
    feed = Feed(presence=presence)
    feed.visit(None, Outcome.POOP)
    reminders = feed.wait(10)
    assert all(r.announce for r in reminders)
    assert "Partner" in presence.asked


def test_reminder_limits_come_from_the_timers():
    feed = Feed(timers=Timers(poop_reminder_max_count=2))
    feed.visit(None, Outcome.POOP)
    assert len(feed.wait(120)) == 2


def test_poop_is_gone_when_a_person_was_at_the_box_and_poop_is_no_longer_seen():
    feed = Feed()
    feed.visit(None, Outcome.POOP)
    assert feed.seen(surface=Outcome.NOTHING) == []  # nobody cleaned it: a bad score is not enough
    feed.seen("person")
    [gone] = feed.seen(surface=Outcome.NOTHING)
    assert (gone.kind, gone.announce) == ("poop_gone", False)
    assert feed.wait(120) == []


def test_poop_still_seen_after_the_person_left_keeps_the_reminders():
    feed = Feed()
    feed.visit(None, Outcome.POOP)
    feed.seen("person")
    assert feed.seen(surface=Outcome.POOP) == []
    assert feed.seen(surface=Outcome.NOTHING) == []  # needs a person at the box again
    assert len(feed.wait(10)) > 0


def test_a_person_away_from_the_box_does_not_count():
    feed = Feed()
    feed.visit(None, Outcome.POOP)
    feed.seen("person", where=OUTSIDE)
    assert feed.seen(surface=Outcome.NOTHING) == []


def test_dog_at_poop_is_urgent_and_said_once_per_approach():
    feed = Feed(timers=Timers(poop_reminder_max_count=0), dog_gone_seconds=60)
    feed.visit(None, Outcome.POOP)
    [dog] = feed.seen("dog")
    assert (dog.kind, dog.urgency, dog.announce) == ("dog_at_poop", Urgency.URGENT, True)
    feed.clock.advance(10)
    assert feed.seen("dog") == []
    feed.clock.advance(30)
    feed.seen()
    feed.clock.advance(30)
    assert feed.seen("dog") == []  # gone only 30 s
    feed.clock.advance(61)
    feed.seen()
    assert feed.kinds(feed.seen("dog")) == ["dog_at_poop"]


def test_dog_at_poop_is_said_again_for_new_poop_after_poop_gone():
    feed = Feed(timers=Timers(poop_reminder_max_count=0), dog_gone_seconds=600)
    feed.visit(None, Outcome.POOP)
    feed.seen("dog")
    feed.seen("person")
    assert feed.kinds(feed.seen(surface=Outcome.NOTHING)) == ["poop_gone"]
    feed.visit(None, Outcome.POOP)
    assert feed.kinds(feed.seen("dog")) == ["dog_at_poop"]


def test_dog_at_poop_is_said_again_when_a_new_poop_starts():
    feed = Feed(timers=Timers(poop_reminder_max_count=0), dog_gone_seconds=600)
    feed.visit(None, Outcome.POOP)
    feed.seen("dog")
    feed.visit(None, Outcome.POOP)
    assert feed.kinds(feed.seen("dog")) == ["dog_at_poop"]


def test_a_dog_at_an_empty_box_is_not_dog_at_poop():
    feed = Feed()
    feed.visit(None, Outcome.PEE)
    assert feed.seen("dog") == []


def test_camera_offline_is_said():
    feed = Feed()
    [event] = feed.tell(obs.CameraOffline(START, START))
    assert (event.kind, event.urgency, event.announce) == ("camera_offline", Urgency.NORMAL, True)


def test_login_expired_is_said_again_once_at_the_reminder_time_if_still_broken():
    feed = Feed(timers=Timers(login_expired_reminder_at=time(18, 0)), zone="Australia/Melbourne")
    # 08:00 UTC is 18:00 in Melbourne, so start just before it.
    feed.clock.advance(-120)
    [first] = feed.tell(obs.LoginExpired(feed.clock.now()))
    assert (first.kind, first.details) == ("login_expired", {})
    [again] = feed.wait(60 * 24 * 2, every=60)
    assert (again.kind, again.details) == ("login_expired", {"reminder": "yes"})
    assert again.at == START


def test_login_expired_reminder_is_dropped_once_pictures_come_back():
    feed = Feed()
    feed.tell(obs.LoginExpired(START))
    feed.clock.advance(60)
    feed.seen()
    assert feed.wait(60 * 24, every=60) == []


def test_standard_event_rules_are_built_from_config(tmp_path):
    config = Config.model_validate(
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
            "listeners": [{"name": "Partner"}],
        }
    )
    registry = default_registry()
    rules = registry.create(EVENT_RULES, "standard", config, {"announce_pee": False})
    assert isinstance(rules, StandardEventRules)
    with pytest.raises(ConfigError, match="announce_pea"):
        registry.create(EVENT_RULES, "standard", config, {"announce_pea": False})


def test_example_config_builds_the_standard_rules_and_sqlite_log(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    config = load_config(Path(__file__).parents[1] / "config.example.toml")
    registry = default_registry()
    rules = registry.create(EVENT_RULES, config.parts.event_rules, config, config.event_rules)
    assert isinstance(rules, StandardEventRules)
    event_log = registry.create(EVENT_LOG, config.parts.event_log, config, config.event_log)
    assert isinstance(event_log, SqliteEventLog)


def test_poop_known_from_before_a_restart_can_be_found_gone():
    feed = Feed(timers=Timers(poop_reminder_max_count=0))
    feed.rules.resume_poop(START, START)
    feed.seen("person")
    feed.clock.advance(10)
    assert feed.kinds(feed.seen(surface=Outcome.NOTHING)) == ["poop_gone"]


def test_poop_known_from_before_a_restart_keeps_dog_at_poop():
    feed = Feed(timers=Timers(poop_reminder_max_count=0))
    feed.rules.resume_poop(START, START)
    assert feed.kinds(feed.seen("dog")) == ["dog_at_poop"]


def test_reminders_after_a_restart_carry_on_without_repeating_past_ones():
    feed = Feed()
    feed.clock.advance(5 * 60)
    feed.rules.resume_poop(START, feed.clock.now())
    reminders = feed.wait(60)
    assert [r.details["number"] for r in reminders] == ["4", "5", "6"]
    assert [round((r.at - START).total_seconds() / 60) for r in reminders] == [8, 16, 32]
