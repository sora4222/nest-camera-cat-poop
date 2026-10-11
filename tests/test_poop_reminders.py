from datetime import UTC, datetime, timedelta

from fake_clock import FakeClock

from catpoop.poop_reminders import PoopReminders

START = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)


def due_minutes(reminders: PoopReminders, minutes: int) -> list[tuple[int, int]]:
    """Check once a minute for `minutes`; (minute, reminder number) for each one due."""
    clock = FakeClock(START)
    said = []
    for minute in range(minutes + 1):
        number = reminders.due(clock.now())
        if number:
            said.append((minute, number))
        clock.advance(60)
    return said


def started(**limits) -> PoopReminders:
    reminders = PoopReminders(**({"first_minutes": 1, "max_minutes": 60, "max_count": 6} | limits))
    reminders.start(START)
    return reminders


def test_reminders_double_their_wait_until_six_are_given():
    assert due_minutes(started(), 120) == [(1, 1), (2, 2), (4, 3), (8, 4), (16, 5), (32, 6)]


def test_reminders_stop_after_the_max_minutes():
    assert due_minutes(started(max_minutes=10, max_count=99), 120) == [
        (1, 1),
        (2, 2),
        (4, 3),
        (8, 4),
    ]


def test_reminders_stop_after_the_max_count():
    assert due_minutes(started(max_count=2), 120) == [(1, 1), (2, 2)]


def test_nothing_is_due_before_start_or_after_stop():
    reminders = PoopReminders(first_minutes=1, max_minutes=60, max_count=6)
    assert due_minutes(reminders, 10) == []
    reminders.start(START)
    reminders.stop()
    assert due_minutes(reminders, 10) == []
    assert not reminders.active


def test_overdue_reminders_are_given_once_not_all_at_once():
    reminders = started()
    assert reminders.due(START + timedelta(minutes=5)) == 3
    assert reminders.due(START + timedelta(minutes=5)) is None
    assert reminders.due(START + timedelta(minutes=8)) == 4
