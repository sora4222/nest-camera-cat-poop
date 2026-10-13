"""Event log "postgres": every Event in a PostgreSQL table.

The database URL comes from `CATPOOP_DATABASE_URL` (in .env); `make db` starts one in
Docker for development.
"""

import os
from collections.abc import Mapping
from typing import Any

import psycopg
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, ValidationError

from catpoop.config import Config, ConfigError
from catpoop.domain import Event, Urgency
from catpoop.registry import DEFAULT, EVENT_LOG

URL_ENV = "CATPOOP_DATABASE_URL"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at TIMESTAMPTZ NOT NULL,
    kind TEXT NOT NULL,
    urgency TEXT NOT NULL,
    announce BOOLEAN NOT NULL,
    details JSONB NOT NULL
)
"""


class PostgresEventLog:
    """Keeps Events in one table, oldest first."""

    def __init__(self, url: str) -> None:
        """Connect to the database at `url` and make the table if it is missing."""
        self._db = psycopg.connect(url, autocommit=True)
        self._db.execute(_SCHEMA)

    def record(self, event: Event) -> None:
        """Store `event`."""
        self._db.execute(
            "INSERT INTO events (at, kind, urgency, announce, details) VALUES (%s, %s, %s, %s, %s)",
            (event.at, event.kind, event.urgency.value, event.announce, Jsonb(event.details)),
        )

    def recent(self, limit: int) -> list[Event]:
        """Up to `limit` Events, newest first."""
        rows = self._db.execute(
            "SELECT at, kind, urgency, announce, details FROM events ORDER BY id DESC LIMIT %s",
            (limit,),
        ).fetchall()
        return [
            Event(kind, Urgency(urgency), at, details, announce)
            for at, kind, urgency, announce, details in rows
        ]

    def close(self) -> None:
        """Close the connection."""
        self._db.close()


class LogOptions(BaseModel):
    """The `[event_log]` options: none yet; the URL is a secret, so it is in .env."""

    model_config = ConfigDict(extra="forbid", frozen=True)


@DEFAULT.part(EVENT_LOG, "postgres")
def _create(config: Config, options: Mapping[str, Any]) -> PostgresEventLog:
    try:
        LogOptions.model_validate(dict(options))
    except ValidationError as error:
        problems = "; ".join(f"event_log.{e['loc'][0]}: {e['msg']}" for e in error.errors())
        raise ConfigError(problems) from None
    url = os.environ.get(URL_ENV)
    if not url:
        raise ConfigError(f"event log 'postgres': set {URL_ENV} in .env (`make db` starts one)")
    try:
        return PostgresEventLog(url)
    except psycopg.OperationalError as error:
        raise ConfigError(f"event log 'postgres': cannot connect: {error}") from None


@DEFAULT.part(EVENT_LOG, "sqlite")
def _replaced(config: Config, options: Mapping[str, Any]) -> PostgresEventLog:
    raise ConfigError(
        'event log "sqlite" was replaced: in config.toml set event_log = "postgres" and remove '
        f"[event_log] path, then set {URL_ENV} in .env (`make db` starts one in Docker)"
    )
