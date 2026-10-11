"""Switches people flip while the watcher runs: Do Not Disturb and Pee announcements.

Kept in a small JSON file in the state folder (`switches.json`), so `catpoop dnd`, the
watcher and later the Alexa skill all read and write the same state. Every read goes to the
file, so a change is seen at once.
"""

import json
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from catpoop.domain import Urgency
from catpoop.state_folder import state_folder

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DoNotDisturb:
    """Do Not Disturb is on until `until`. `allow`: Urgencies still spoken; None for the
    `[communications] dnd_allow` default."""

    until: datetime
    allow: tuple[Urgency, ...] | None


class Switches:
    """Reads and writes the switches file at `path`."""

    def __init__(self, path: Path) -> None:
        """Use the file at `path`; it is made on the first change."""
        self.path = path

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
            until = datetime.fromisoformat(dnd["until"])
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
        data = self._read() | values
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(f".{self.path.name}.{os.getpid()}")
        temp.write_text(json.dumps(data))
        os.replace(temp, self.path)
