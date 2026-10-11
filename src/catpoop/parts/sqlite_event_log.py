"""Event log "sqlite": every Event in a small SQLite file on the server.

`[event_log] path` is the file; a relative path (default `events.sqlite`) is inside
`$XDG_STATE_HOME/catpoop` (else `~/.local/state/catpoop`), outside any worktree.
"""

import json
import os
import sqlite3
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from catpoop.config import Config
from catpoop.domain import Event, Urgency
from catpoop.registry import DEFAULT, EVENT_LOG

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    kind TEXT NOT NULL,
    urgency TEXT NOT NULL,
    announce INTEGER NOT NULL,
    details TEXT NOT NULL
)
"""


def state_folder() -> Path:
    """`$XDG_STATE_HOME/catpoop`, else `~/.local/state/catpoop`."""
    base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / "catpoop"


def default_path() -> Path:
    """Where the event log is kept when no path is set."""
    return state_folder() / "events.sqlite"


class SqliteEventLog:
    """Keeps Events in one table, oldest first."""

    def __init__(self, path: Path) -> None:
        """Open (or create) the database at `path`, making its folder if needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute(_SCHEMA)
        self._db.commit()

    def record(self, event: Event) -> None:
        """Store `event`."""
        self._db.execute(
            "INSERT INTO events (at, kind, urgency, announce, details) VALUES (?, ?, ?, ?, ?)",
            (
                event.at.isoformat(),
                event.kind,
                event.urgency.value,
                int(event.announce),
                json.dumps(event.details),
            ),
        )
        self._db.commit()

    def recent(self, limit: int) -> list[Event]:
        """Up to `limit` Events, newest first."""
        rows = self._db.execute(
            "SELECT at, kind, urgency, announce, details FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [
            Event(kind, Urgency(urgency), datetime.fromisoformat(at), json.loads(details), bool(a))
            for at, kind, urgency, a, details in rows
        ]

    def close(self) -> None:
        """Close the database."""
        self._db.close()


@DEFAULT.part(EVENT_LOG, "sqlite")
def _create(config: Config, options: Mapping[str, Any]) -> SqliteEventLog:
    path = Path(options.get("path", "events.sqlite")).expanduser()
    return SqliteEventLog(path if path.is_absolute() else state_folder() / path)
