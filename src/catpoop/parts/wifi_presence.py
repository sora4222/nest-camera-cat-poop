"""Presence check "wifi": a Listener is Home while their phone was seen on the home Wi-Fi lately.

Phones sleep their Wi-Fi, so a phone counts as Home until `away_after` has passed since it
was last seen. If looking fails, every Listener is Unknown (counts as Away) until it works again.
"""

import ipaddress
import logging
import threading
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from catpoop.clock import Clock, SystemClock
from catpoop.config import Config, ConfigError
from catpoop.domain import Presence
from catpoop.parts.wifi_neighbours import NeighbourTable
from catpoop.registry import DEFAULT, PRESENCE

log = logging.getLogger(__name__)


class PhoneSeer(Protocol):
    """Looks for a phone on the home network."""

    def seen(self, address: str) -> bool:
        """Whether the phone at IP `address` answers now. Raises if it cannot look at all."""
        ...


class WifiPresence:
    """`PresenceCheck` from when each Listener's phone was last seen. `look` refreshes it."""

    def __init__(
        self, phones: Mapping[str, str], seer: PhoneSeer, clock: Clock, away_after: timedelta
    ) -> None:
        """`phones` maps Listener name to phone IP address."""
        self._phones = dict(phones)
        self._seer = seer
        self._clock = clock
        self._away_after = away_after
        self._last_seen: dict[str, datetime] = {}
        self._working: bool | None = None  # None: not looked yet
        self._lock = threading.Lock()
        self._stop = threading.Event()

    def look(self) -> None:
        """Look for every phone now. Never raises."""
        seen_at: dict[str, datetime] = {}
        try:
            for name, address in self._phones.items():
                if self._seer.seen(address):
                    seen_at[name] = self._clock.now()
        except Exception as error:
            if self._working is not False:
                log.warning("wifi presence: cannot look for phones, everyone is Unknown: %s", error)
            with self._lock:
                self._working = False
            return
        with self._lock:
            self._last_seen.update(seen_at)
            self._working = True

    def check(self, listener: str) -> Presence:
        """Home if the phone was seen within `away_after`; Unknown if looking is not working."""
        with self._lock:
            working, last = self._working, self._last_seen.get(listener)
        if working is not True or listener not in self._phones:
            return Presence.UNKNOWN
        if last is not None and self._clock.now() - last < self._away_after:
            return Presence.HOME
        return Presence.AWAY

    def start(self, every_seconds: float) -> None:
        """Look for the phones every `every_seconds` on a background thread, until `close`."""
        threading.Thread(
            target=self._run, args=(every_seconds,), name="wifi-presence", daemon=True
        ).start()

    def close(self) -> None:
        """Stop looking."""
        self._stop.set()

    def _run(self, every_seconds: float) -> None:
        while not self._stop.is_set():
            self.look()
            self._stop.wait(every_seconds)


class WifiOptions(BaseModel):
    """The `[presence]` options for "wifi"."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    away_after_minutes: float = Field(10.0, gt=0)
    look_seconds: float = Field(60.0, gt=0)
    port: int = Field(62078, gt=0, lt=65536)
    timeout_seconds: float = Field(1.0, gt=0)


def _phones(config: Config) -> dict[str, str]:
    """Listener name -> phone IP, from `phone_ip` in each `[[listeners]]` entry that has one."""
    phones = {}
    for listener in config.listeners:
        address = (listener.model_extra or {}).get("phone_ip")
        if address is None:
            continue
        try:
            phones[listener.name] = str(ipaddress.ip_address(address))
        except ValueError:
            raise ConfigError(
                f"listeners {listener.name}: phone_ip {address!r} is not an IP address"
            ) from None
    return phones


def _options(options: Mapping[str, Any]) -> WifiOptions:
    try:
        return WifiOptions.model_validate(dict(options))
    except ValidationError as error:
        problems = "; ".join(f"presence.{e['loc'][0]}: {e['msg']}" for e in error.errors())
        raise ConfigError(problems) from None


def build_wifi_presence(
    config: Config, options: Mapping[str, Any], seer: PhoneSeer, clock: Clock
) -> WifiPresence:
    """A `WifiPresence` from config, not yet looking. Raises `ConfigError`."""
    parsed = _options(options)
    return WifiPresence(_phones(config), seer, clock, timedelta(minutes=parsed.away_after_minutes))


@DEFAULT.part(PRESENCE, "wifi")
def _create(config: Config, options: Mapping[str, Any]) -> WifiPresence:
    parsed = _options(options)
    seer = NeighbourTable(port=parsed.port, timeout_seconds=parsed.timeout_seconds)
    presence = build_wifi_presence(config, options, seer, SystemClock())
    presence.start(parsed.look_seconds)
    return presence
