"""Tell Alexa a virtual sensor saw motion, so the routine on it runs.

Each trigger sends a DETECTED ChangeReport to the Alexa Event Gateway now and a
NOT_DETECTED one 30 seconds later (Amazon's minimum), so the sensor is at rest again
for the next message.
"""

import logging
import threading
import uuid
from collections.abc import Callable
from typing import Any, Literal, Protocol

import httpx

from catpoop.alexa_smart_home.directives import not_detected
from catpoop.clock import Clock

Region = Literal["NA", "EU", "FE"]
URLS: dict[str, str] = {
    "NA": "https://api.amazonalexa.com/v3/events",
    "EU": "https://api.eu.amazonalexa.com/v3/events",
    "FE": "https://api.fe.amazonalexa.com/v3/events",
}
"""By the region of the Amazon account: EU includes India; FE is Australia and Japan."""
REST_AFTER = 30.0
"""Seconds between DETECTED and NOT_DETECTED; Amazon asks for at least 30."""
Later = Callable[[float, Callable[[], None]], None]
log = logging.getLogger(__name__)


def _in_background(seconds: float, action: Callable[[], None]) -> None:
    timer = threading.Timer(seconds, action)
    timer.daemon = True
    timer.start()


class GatewayError(Exception):
    """Alexa did not take the report."""


class AccessToken(Protocol):
    """Gives a current Login with Amazon token (`Grants`)."""

    def access_token(self) -> str:
        """The token."""
        ...


class EventGateway:
    """Sends sensor changes for one Amazon account."""

    def __init__(
        self,
        tokens: AccessToken,
        region: Region,
        clock: Clock,
        http: httpx.Client,
        later: Later = _in_background,
    ) -> None:
        """Report to the gateway for `region`; `later` runs the reset after a delay."""
        self._tokens = tokens
        self._url = URLS[region]
        self._clock = clock
        self._http = http
        self._later = later

    def trigger(self, endpoint_id: str) -> None:
        """Motion on `endpoint_id` now, rest later; raise `GatewayError` if refused."""
        rest = not_detected(self._clock)
        self._report(endpoint_id, {**rest[0], "value": "DETECTED"}, rest[1])
        self._later(REST_AFTER, lambda: self._rest(endpoint_id))

    def _rest(self, endpoint_id: str) -> None:
        rest = not_detected(self._clock)  # sampled when it really happens
        try:
            self._report(endpoint_id, rest[0], rest[1])
        except Exception as error:
            log.warning("could not set %s back to rest: %s", endpoint_id, error)

    def _report(self, endpoint_id: str, change: dict[str, Any], health: dict[str, Any]) -> None:
        token = self._tokens.access_token()
        header = {
            "namespace": "Alexa",
            "name": "ChangeReport",
            "messageId": str(uuid.uuid4()),
            "payloadVersion": "3",
        }
        endpoint = {"scope": {"type": "BearerToken", "token": token}, "endpointId": endpoint_id}
        payload = {"change": {"cause": {"type": "PHYSICAL_INTERACTION"}, "properties": [change]}}
        body = {
            "event": {"header": header, "endpoint": endpoint, "payload": payload},
            "context": {"properties": [health]},
        }
        try:
            response = self._http.post(
                self._url, json=body, headers={"Authorization": f"Bearer {token}"}
            )
        except httpx.HTTPError as error:
            raise GatewayError(f"Alexa events: {type(error).__name__}") from None
        if response.is_error:
            raise GatewayError(f"Alexa events: {response.status_code} for {endpoint_id}")
