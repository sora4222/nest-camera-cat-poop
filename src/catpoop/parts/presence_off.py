"""Presence check that is switched off: every Listener is Unknown (counts as Away)."""

from collections.abc import Mapping
from typing import Any

from catpoop.config import Config
from catpoop.domain import Presence
from catpoop.registry import DEFAULT, PRESENCE


class PresenceOff:
    """Always says Unknown."""

    def check(self, listener: str) -> Presence:
        """Unknown, whoever `listener` is."""
        return Presence.UNKNOWN


@DEFAULT.part(PRESENCE, "off")
def _create(config: Config, options: Mapping[str, Any]) -> PresenceOff:
    return PresenceOff()
