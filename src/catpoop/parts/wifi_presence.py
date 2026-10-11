"""Presence check "wifi": a Listener is Home while their phone was seen on the home Wi-Fi lately.

Phones sleep their Wi-Fi, so a phone counts as Home until `away_after` has passed since it
was last seen. If looking fails, every Listener is Unknown (counts as Away) until it works again.
"""

import logging
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Protocol

from catpoop.clock import Clock
from catpoop.domain import Presence

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

    def look(self) -> None:
        """Look for every phone now. Never raises."""
        try:
            for name, address in self._phones.items():
                if self._seer.seen(address):
                    self._last_seen[name] = self._clock.now()
        except Exception as error:
            if self._working is not False:
                log.warning("wifi presence: cannot look for phones, everyone is Unknown: %s", error)
            self._working = False
            return
        self._working = True

    def check(self, listener: str) -> Presence:
        """Home if the phone was seen within `away_after`; Unknown if looking is not working."""
        if self._working is not True or listener not in self._phones:
            return Presence.UNKNOWN
        last = self._last_seen.get(listener)
        if last is not None and self._clock.now() - last < self._away_after:
            return Presence.HOME
        return Presence.AWAY
