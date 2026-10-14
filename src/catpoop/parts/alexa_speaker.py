"""Speaker kind "alexa": fire the virtual sensor whose Alexa routine says the message.

Free and official: the Smart Home skill (docs/alexa-smart-home.md) shows one sensor per
message kind, and an Alexa routine on each sensor says its text on the Echo.
"""

import os
from collections.abc import Mapping
from typing import Any, Protocol

import httpx

from catpoop.alexa_smart_home.event_gateway import EventGateway
from catpoop.alexa_smart_home.grants import Grants
from catpoop.alexa_smart_home.sensors import kind_of, sensors
from catpoop.clock import SystemClock
from catpoop.config import Config, ConfigError, Household
from catpoop.registry import DEFAULT, SPEAKER


class NoSensor(Exception):
    """The text matches no message kind, so no routine can say it."""


class Gateway(Protocol):
    """Fires a sensor (`EventGateway`)."""

    def trigger(self, endpoint_id: str) -> None:
        """Motion on `endpoint_id`."""
        ...


class AlexaSpeaker:
    """Says a message by firing its sensor; the routine on the sensor speaks."""

    def __init__(
        self, name: str, templates: Mapping[str, str], household: Household, gateway: Gateway
    ) -> None:
        """Map texts made from `templates` to their sensors and fire them on `gateway`."""
        self.name = name
        self._templates = dict(templates)
        self._household = household
        self._ids = {s.kind: s.endpoint_id for s in sensors(templates)}
        self._gateway = gateway

    def say(self, text: str) -> None:
        """Fire the sensor for `text`, or raise `NoSensor` / `GatewayError`."""
        kind = kind_of(text, self._templates, self._household)
        if kind is None:
            raise NoSensor(f"Alexa: no [messages] kind makes {text!r}")
        self._gateway.trigger(self._ids[kind])


@DEFAULT.part(SPEAKER, "alexa")
def _create(config: Config, options: Mapping[str, Any]) -> AlexaSpeaker:
    region = options.get("region", "NA")
    if region not in ("NA", "EU", "FE"):
        raise ConfigError(f"speaker {options['name']!r}: region must be NA, EU or FE")
    clock = SystemClock()
    grants = Grants.from_env(os.environ, clock)
    gateway = EventGateway(grants, region, clock, httpx.Client(timeout=10))
    return AlexaSpeaker(options["name"], config.messages, config.household, gateway)
