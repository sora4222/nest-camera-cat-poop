"""Speaker kind "alexa_web": an Alexa device, through Amazon's Alexa web API.

The refresh token comes from `CATPOOP_ALEXA_REFRESH_TOKEN` in `.env`.
"""

import os
from collections.abc import Mapping
from typing import Any, Protocol

from catpoop.alexa_web import AlexaWeb
from catpoop.config import Config, ConfigError
from catpoop.registry import DEFAULT, SPEAKER

TOKEN_ENV = "CATPOOP_ALEXA_REFRESH_TOKEN"


class Web(Protocol):
    """What the Speaker needs from `AlexaWeb`."""

    def speak(self, device: str, text: str) -> None:
        """Say `text` on `device`."""
        ...


class AlexaWebSpeaker:
    """Says text on one Alexa device, in Alexa's voice."""

    def __init__(self, name: str, device: str, web: Web) -> None:
        """Speak on `device` (its name in the Alexa app) through `web`."""
        self.name = name
        self.device = device
        self.web = web

    def say(self, text: str) -> None:
        """Say `text`, or raise `AlexaWebError`."""
        self.web.speak(self.device, text)


@DEFAULT.part(SPEAKER, "alexa_web")
def _create(config: Config, options: Mapping[str, Any]) -> AlexaWebSpeaker:
    token = os.environ.get(TOKEN_ENV)
    if not token:
        raise ConfigError(f"speaker {options['name']!r}: set {TOKEN_ENV} in .env")
    web = AlexaWeb(token, options.get("domain", "amazon.com"), options.get("locale", "en-US"))
    return AlexaWebSpeaker(options["name"], options.get("device", options["name"]), web)
