"""Speaker that writes messages to the log instead of saying them. For trying things out."""

import logging
from collections.abc import Mapping
from typing import Any

from catpoop.config import Config
from catpoop.registry import DEFAULT, SPEAKER

logger = logging.getLogger(__name__)


class LogSpeaker:
    """Logs each message with the Speaker's name."""

    def __init__(self, name: str) -> None:
        """Make a Speaker called `name`."""
        self.name = name

    def say(self, text: str) -> None:
        """Log `text`."""
        logger.info("%s: %s", self.name, text)


@DEFAULT.part(SPEAKER, "log")
def _create(config: Config, options: Mapping[str, Any]) -> LogSpeaker:
    return LogSpeaker(options["name"])
