"""`POST /alexa/smart-home`: directives forwarded by our Lambda, which sends a shared secret.

Amazon only sends Smart Home directives to AWS Lambda, so a small Lambda
(`alexa/smart_home_lambda.py`) forwards them here through the tunnel. Requests without
the secret get 401 and never reach the skill.
"""

import hmac
import json
import logging
from collections.abc import Mapping
from typing import Any, Protocol

from catpoop.alexa_skill.endpoint import EndpointResponse

log = logging.getLogger(__name__)

PATH = "/alexa/smart-home"


class Skill(Protocol):
    """Answers a directive (`SmartHome`)."""

    def answer(self, request: dict[str, Any]) -> dict[str, Any]:
        """The response."""
        ...


class SmartHomeEndpoint:
    """Checks the shared secret, then lets the skill answer."""

    def __init__(self, secret: str, skill: Skill) -> None:
        """Accept requests whose `Authorization` is `Bearer <secret>`."""
        self._expected = f"Bearer {secret}".encode()
        self._skill = skill

    def __repr__(self) -> str:
        """Never the secret."""
        return "SmartHomeEndpoint()"

    def handle(
        self, method: str, path: str, headers: Mapping[str, str], body: bytes
    ) -> EndpointResponse:
        """The response to one forwarded directive."""
        if path != PATH:
            return EndpointResponse(404, b"not found")
        if method != "POST":
            return EndpointResponse(405, b"method not allowed")
        given = {k.lower(): v for k, v in headers.items()}.get("authorization", "")
        if not hmac.compare_digest(given.encode(), self._expected):
            log.warning("Smart Home request without the right secret")
            return EndpointResponse(401, b"unauthorized")
        try:
            answer = self._skill.answer(json.loads(body))
        except Exception:
            log.exception("the Smart Home skill failed")
            return EndpointResponse(500, b"error")
        return EndpointResponse(200, json.dumps(answer).encode(), "application/json")
