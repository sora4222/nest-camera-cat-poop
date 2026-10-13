"""The one public HTTP endpoint, `POST /alexa`: verify the request, then let the skill answer.

A request that fails verification is 400 (as Amazon's certification tests expect) and never
reaches the skill. FastAPI answers 404 for other paths and 405 for other methods.
"""

import json
import logging
from collections.abc import Mapping
from typing import Any, Protocol

from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse

from catpoop.alexa_skill.body_limit import read_body
from catpoop.alexa_skill.request_verifier import RequestRejected

log = logging.getLogger(__name__)

PATH = "/alexa"
MAX_BODY = 64 * 1024


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


router = APIRouter()


@router.post(PATH)
async def alexa(request: Request) -> Response:
    """Answer one Alexa request with `app.state.skill`, checked by `app.state.verifier` first.

    The handler is async, so it runs on the server's one event loop: the skill answers one
    request at a time and two intents never change the switches together.
    """
    verifier: Verifier = request.app.state.verifier
    skill: Skill = request.app.state.skill
    body = await read_body(request, MAX_BODY)
    try:
        payload = verifier.verify(request.headers, body)
    except RequestRejected as error:
        log.warning("Alexa request rejected: %s", error)
        return PlainTextResponse("bad request", 400)
    try:
        answer = skill.respond(payload)
    except Exception:
        log.exception("the Alexa skill failed")
        return PlainTextResponse("error", 500)
    return Response(json.dumps(answer), media_type="application/json;charset=UTF-8")
