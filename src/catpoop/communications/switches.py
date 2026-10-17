"""Switches people flip while the watcher runs: Do Not Disturb, quiet topics and Pee announcements.

Kept in a small JSON file in the state folder (`switches.json`), so `catpoop dnd`, the
watcher and the Alexa skill all read and write the same state. Every read goes to the
file, so a change is seen at once. Changes hold a lock file, opened afresh each time, so it
keeps out other threads and other processes alike, and two changes at once both stay.
"""

import fcntl
import json
import logging
import os
import tempfile
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from catpoop.domain import Urgency
from catpoop.state_folder import state_folder

log = logging.getLogger(__name__)

type Topic = Literal["poop", "visits"]


@dataclass(frozen=True)
class DoNotDisturb:
    """Do Not Disturb is on until `until`.

    `allow`: Urgencies still spoken; None for the `[communications] dnd_allow` default.
    """

    until: datetime
    allow: tuple[Urgency, ...] | None


def _until(value: str) -> datetime:
    """The time in `value`; ValueError if it has no time zone (it can't be compared)."""
    until = datetime.fromisoformat(value)
    if until.tzinfo is None:
        raise ValueError(f"{value!r} has no time zone")
    return until


class Switches:
    """Reads and writes the switches file at `path`."""

    def __init__(self, path: Path) -> None:
        """Use the file at `path`; it is made on the first change."""
        self.path = path

    @property
    def lock_path(self) -> Path:
        """The lock file next to the switches file; changes hold it."""
        return self.path.with_name(f".{self.path.name}.lock")

    @classmethod
    def default(cls) -> "Switches":
        """The switches in the user's state folder."""
        return cls(state_folder() / "switches.json")

    def do_not_disturb(self, at: datetime) -> DoNotDisturb | None:
        """Do Not Disturb if it is on at `at`, else None."""
        dnd = self._read().get("dnd")
        if not dnd:
            return None
        try:
            until = _until(dnd["until"])
            allow = dnd.get("allow")
            allowed = None if allow is None else tuple(map(Urgency, allow))
        except (KeyError, TypeError, ValueError) as error:
            log.warning("Do Not Disturb in the switches file %s is broken: %s", self.path, error)
            return None
        return None if at >= until else DoNotDisturb(until, allowed)

    def set_do_not_disturb(self, until: datetime, allow: Iterable[Urgency] | None = None) -> None:
        """Turn Do Not Disturb on until `until`, letting `allow` Urgencies through."""
        allow_values = None if allow is None else [urgency.value for urgency in allow]
        self._change(dnd={"until": until.isoformat(), "allow": allow_values})

    def clear_do_not_disturb(self) -> None:
        """Turn Do Not Disturb off."""
        self._change(dnd=None)

    def quiet_until(self, topic: Topic, at: datetime) -> datetime | None:
        """When `topic` stops being quiet, if it is quiet at `at`, else None."""
        value = self._read().get(f"quiet_{topic}")
        if not value:
            return None
        try:
            until = _until(value)
        except (TypeError, ValueError) as error:
            log.warning("quiet %s in the switches file %s is broken: %s", topic, self.path, error)
            return None
        return None if at >= until else until

    def set_quiet(self, topic: Topic, until: datetime) -> None:
        """Keep `topic` quiet until `until`."""
        self._change(**{f"quiet_{topic}": until.isoformat()})

    def clear_quiet(self, topic: Topic) -> None:
        """Let `topic` be announced again."""
        self._change(**{f"quiet_{topic}": None})

    def pee_announcements(self) -> bool:
        """Whether Pee announcements are on (the default)."""
        return bool(self._read().get("pee_announcements", True))

    def set_pee_announcements(self, on: bool) -> None:
        """Turn Pee announcements on or off."""
        self._change(pee_announcements=on)

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text())
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as error:
            log.warning("cannot read the switches file %s: %s", self.path, error)
            return {}
        return data if isinstance(data, dict) else {}

    def _change(self, **values: Any) -> None:
        """Write the file with `values` changed, all at once (a reader never sees half)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._locked():
            data = self._read() | values
            with tempfile.NamedTemporaryFile(
                "w", dir=self.path.parent, prefix=f".{self.path.name}.", delete=False
            ) as temp:
                temp.write(json.dumps(data))
            try:
                os.replace(temp.name, self.path)
            except OSError:
                Path(temp.name).unlink(missing_ok=True)
                raise

    @contextmanager
    def _locked(self) -> Generator[None]:
        """Hold the lock file (blocks other threads and processes; closing it lets go)."""
        with self.lock_path.open("a") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            yield
