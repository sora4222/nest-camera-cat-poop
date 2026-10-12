"""Tell Alexa a virtual sensor saw motion, so the routine on it runs.

Each trigger sends two ChangeReports to the Alexa Event Gateway: DETECTED, then
NOT_DETECTED, so the sensor is at rest again for the next message.
"""

import uuid
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
"""By the region of the Amazon account: FE is Australia, Japan and India."""


class GatewayError(Exception):
    """Alexa did not take the report."""


class AccessToken(Protocol):
    """Gives a current Login with Amazon token (`Grants`)."""

    def access_token(self) -> str:
        """The token."""
        ...


class EventGateway:
    """Sends sensor changes for one Amazon account."""

    def __init__(self, tokens: AccessToken, region: Region, clock: Clock, http: httpx.Client):
        """Report to the gateway for `region` with tokens from `tokens`."""
        self._tokens = tokens
        self._url = URLS[region]
        self._clock = clock
        self._http = http

    def trigger(self, endpoint_id: str) -> None:
        """Motion on `endpoint_id`, then rest; raise `GatewayError` if refused."""
        rest = not_detected(self._clock)
        motion = {**rest[0], "value": "DETECTED"}
        self._report(endpoint_id, motion, rest[1])
        self._report(endpoint_id, rest[0], rest[1])

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
