from datetime import UTC, datetime, timedelta

from catpoop.config import Config
from catpoop.domain import Event, Urgency
from catpoop.parts.sqlite_event_log import SqliteEventLog, default_path
from catpoop.registry import EVENT_LOG, default_registry

AT = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)


def events() -> list[Event]:
    return [
        Event("poop", Urgency.NORMAL, AT),
        Event("visit_ended", Urgency.INFO, AT + timedelta(seconds=1), {"outcome": "pee"}, False),
        Event("dog_at_poop", Urgency.URGENT, AT + timedelta(seconds=2)),
    ]


def test_events_come_back_newest_first(tmp_path):
    log = SqliteEventLog(tmp_path / "events.sqlite")
    for event in events():
        log.record(event)
    assert log.recent(2) == events()[::-1][:2]


def test_events_are_kept_after_a_restart(tmp_path):
    path = tmp_path / "state" / "events.sqlite"
    first = SqliteEventLog(path)
    for event in events():
        first.record(event)
    first.close()
    assert SqliteEventLog(path).recent(10) == events()[::-1]


def test_default_path_is_in_the_users_state_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert default_path() == tmp_path / "catpoop" / "events.sqlite"
    monkeypatch.delenv("XDG_STATE_HOME")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert default_path() == tmp_path / ".local" / "state" / "catpoop" / "events.sqlite"


def test_sqlite_event_log_is_built_from_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    config = Config.model_validate(
        {
            "parts": dict.fromkeys(
                ["camera", "detector", "event_rules", "event_log", "presence", "communications"],
                "x",
            ),
            "paths": {"private_data_store": str(tmp_path)},
        }
    )
    registry = default_registry()
    log = registry.create(EVENT_LOG, "sqlite", config, {"path": "mine.sqlite"})
    log.record(events()[0])
    assert (tmp_path / "xdg" / "catpoop" / "mine.sqlite").is_file()
    absolute = tmp_path / "abs.sqlite"
    registry.create(EVENT_LOG, "sqlite", config, {"path": str(absolute)}).record(events()[0])
    assert absolute.is_file()
