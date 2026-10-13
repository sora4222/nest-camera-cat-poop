"""The one public HTTP endpoint, `POST /alexa`: verify the request, then let the skill answer.

Every other path is 404 and every other method 405, before anything is checked. A request
that fails verification is 400 (as Amazon's certification tests expect) and never reaches
the skill.
"""

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from catpoop.alexa_skill.request_verifier import RequestRejected

log = logging.getLogger(__name__)

PATH = "/alexa"
MAX_BODY = 64 * 1024
"""Alexa requests are a few KB; bigger bodies are refused unread."""


class Verifier(Protocol):
    """Checks a request is from Alexa for our skill (`RequestVerifier`)."""

    def verify(self, headers: Mapping[str, str], body: bytes) -> dict[str, Any]:
        """The request as JSON, or raise `RequestRejected`."""
        ...


class Skill(Protocol):
    """Answers a verified request (`AlexaSkill`)."""

    def respond(self, request: dict[str, Any]) -> dict[str, Any]:
        """The response envelope."""
        ...


@dataclass(frozen=True)
class EndpointResponse:
    """What to send back."""

    status: int
    body: bytes = b""
    content_type: str = "text/plain; charset=utf-8"


class AlexaEndpoint:
    """Turns one HTTP request into one HTTP response."""

    def __init__(self, verifier: Verifier, skill: Skill) -> None:
        """Check every request with `verifier` before `skill` sees it."""
        self._verifier = verifier
        self._skill = skill

    def handle(
        self, method: str, path: str, headers: Mapping[str, str], body: bytes
    ) -> EndpointResponse:
        """The response to `method path` with `headers` and `body`."""
        if path != PATH:
            return EndpointResponse(404, b"not found")
        if method != "POST":
            return EndpointResponse(405, b"method not allowed")
        try:
            request = self._verifier.verify(headers, body)
        except RequestRejected as error:
            log.warning("Alexa request rejected: %s", error)
            return EndpointResponse(400, b"bad request")
        try:
            answer = self._skill.respond(request)
        except Exception:
            log.exception("the Alexa skill failed")
            return EndpointResponse(500, b"error")
        return EndpointResponse(200, json.dumps(answer).encode(), "application/json;charset=UTF-8")
