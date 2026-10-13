"""Event log "postgres": every Event in a PostgreSQL table.

The database URL comes from `CATPOOP_DATABASE_URL` (in .env); `make db` starts one in
Docker for development. The table is made by the Alembic migrations, run on start.
"""

import os
import threading
from collections.abc import Mapping
from typing import Any

import psycopg
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, ValidationError

from catpoop.config import Config, ConfigError
from catpoop.database import upgrade
from catpoop.domain import Event, Urgency
from catpoop.registry import DEFAULT, EVENT_LOG

URL_ENV = "CATPOOP_DATABASE_URL"


class PostgresEventLog:
    """Keeps Events in one table, oldest first. Safe to share between threads."""

    def __init__(self, url: str) -> None:
        """Connect to the database at `url`, already upgraded (`catpoop.database.upgrade`)."""
        self._db = psycopg.connect(url, autocommit=True)
        self._lock = threading.Lock()

    def record(self, event: Event) -> None:
        """Store `event`."""
        with self._lock:
            self._db.execute(
                "INSERT INTO events (at, kind, urgency, announce, details) "
                "VALUES (%s, %s, %s, %s, %s)",
                (event.at, event.kind, event.urgency.value, event.announce, Jsonb(event.details)),
            )

    def recent(self, limit: int) -> list[Event]:
        """Up to `limit` Events, newest first."""
        with self._lock:
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
        with self._lock:
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
        event_log = PostgresEventLog(url)
    except psycopg.OperationalError as error:
        raise ConfigError(f"event log 'postgres': cannot connect: {error}") from None
    upgrade(url)
    return event_log


@DEFAULT.part(EVENT_LOG, "sqlite")
def _replaced(config: Config, options: Mapping[str, Any]) -> PostgresEventLog:
    raise ConfigError(
        'event log "sqlite" was replaced: in config.toml set event_log = "postgres" and remove '
        f"[event_log] path, then set {URL_ENV} in .env (`make db` starts one in Docker)"
    )
