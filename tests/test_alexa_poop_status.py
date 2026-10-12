from datetime import UTC, datetime, timedelta

from catpoop.alexa_skill.poop_status import LitterBoxStatus, litter_box_status
from catpoop.domain import Event, Urgency
from catpoop.parts.memory_event_log import MemoryEventLog

T0 = datetime(2026, 10, 11, 8, 0, tzinfo=UTC)


def log_of(*kinds: str) -> MemoryEventLog:
    log = MemoryEventLog()
    for minute, kind in enumerate(kinds):
        log.record(Event(kind, Urgency.INFO, T0 + timedelta(minutes=minute)))
    return log


def at(minute: int) -> datetime:
    return T0 + timedelta(minutes=minute)


def test_an_empty_log_knows_of_no_poop_or_visit():
    assert litter_box_status(MemoryEventLog()) == LitterBoxStatus(None, None)


def test_poop_is_in_the_box_since_the_poop_event():
    log = log_of("visit_started", "visit_ended", "poop", "poop_reminder")
    assert litter_box_status(log) == LitterBoxStatus(at(2), last_visit=at(1), newest_poop=at(2))


def test_poop_gone_after_poop_means_the_box_is_clean():
    log = log_of("visit_ended", "poop", "poop_gone", "visit_ended")
    assert litter_box_status(log) == LitterBoxStatus(poop_since=None, last_visit=at(3))


def test_new_poop_after_poop_gone_counts():
    log = log_of("poop", "poop_gone", "visit_ended", "poop")
    assert litter_box_status(log).poop_since == at(3)


def test_only_the_newest_events_are_looked_at():
    log = log_of("poop", *["camera_offline"] * 10)
    assert litter_box_status(log, look_back=5) == LitterBoxStatus(None, None)


def test_poop_since_is_the_first_poop_after_the_last_poop_gone():
    log = log_of("poop", "poop_gone", "poop", "poop_reminder", "poop")
    assert litter_box_status(log).poop_since == at(2)


def test_newest_poop_is_the_last_poop_still_in_the_box():
    log = log_of("poop", "poop_reminder", "poop", "poop_reminder")
    assert litter_box_status(log).newest_poop == at(2)


def test_no_newest_poop_once_it_is_gone():
    log = log_of("poop", "poop_gone")
    assert litter_box_status(log).newest_poop is None
