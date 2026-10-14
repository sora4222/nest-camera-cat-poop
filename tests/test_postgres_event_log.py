from datetime import UTC, datetime, timedelta

import pytest

from catpoop.config import Config, ConfigError
from catpoop.database import upgrade
from catpoop.domain import Event, Urgency
from catpoop.parts.postgres_event_log import URL_ENV, PostgresEventLog
from catpoop.registry import EVENT_LOG, default_registry

AT = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)


@pytest.fixture
def url(database_url: str) -> str:
    """An empty schema with the migrations applied."""
    upgrade(database_url)
    return database_url


def events() -> list[Event]:
    return [
        Event("poop", Urgency.NORMAL, AT),
        Event("visit_ended", Urgency.INFO, AT + timedelta(seconds=1), {"outcome": "pee"}, False),
        Event("dog_at_poop", Urgency.URGENT, AT + timedelta(seconds=2)),
    ]


def config() -> Config:
    return Config.model_validate(
        {
            "parts": dict.fromkeys(
                ["camera", "detector", "event_rules", "event_log", "presence", "communications"],
                "x",
            ),
            "paths": {"private_data_store": "/data/store"},
        }
    )


def test_events_come_back_newest_first(url):
    log = PostgresEventLog(url)
    for event in events():
        log.record(event)
    assert log.recent(2) == events()[::-1][:2]


def test_events_are_kept_after_a_restart(url):
    first = PostgresEventLog(url)
    for event in events():
        first.record(event)
    first.close()
    assert PostgresEventLog(url).recent(10) == events()[::-1]


def test_postgres_event_log_is_built_from_config_with_the_url_from_env(url, monkeypatch):
    monkeypatch.setenv(URL_ENV, url)
    log = default_registry().create(EVENT_LOG, "postgres", config(), {})
    log.record(events()[0])
    assert PostgresEventLog(url).recent(1) == [events()[0]]


def test_without_the_url_it_is_a_config_error(monkeypatch):
    monkeypatch.delenv(URL_ENV, raising=False)
    with pytest.raises(ConfigError, match=URL_ENV):
        default_registry().create(EVENT_LOG, "postgres", config(), {})


def test_unknown_event_log_options_are_a_config_error(monkeypatch):
    monkeypatch.setenv(URL_ENV, "postgresql://nowhere/x")
    with pytest.raises(ConfigError, match=r"event_log\.path"):
        default_registry().create(EVENT_LOG, "postgres", config(), {"path": "events.sqlite"})


def test_a_database_it_cannot_reach_is_a_config_error(monkeypatch):
    monkeypatch.setenv(URL_ENV, "postgresql://catpoop@127.0.0.1:1/catpoop?connect_timeout=2")
    with pytest.raises(ConfigError, match="event log"):
        default_registry().create(EVENT_LOG, "postgres", config(), {})


def test_an_old_sqlite_config_says_how_to_move_to_postgres():
    with pytest.raises(ConfigError, match=r'event_log = "postgres".*' + URL_ENV):
        default_registry().create(EVENT_LOG, "sqlite", config(), {"path": "events.sqlite"})
