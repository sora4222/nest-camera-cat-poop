"""`POST /alexa/smart-home`: directives forwarded by our Lambda, which sends a shared secret.

The app that includes `router` sets `app.state.smart_home_secret` and `app.state.smart_home`.

Amazon only sends Smart Home directives to AWS Lambda, so a small Lambda
(`alexa/smart_home_lambda.py`) forwards them here through the tunnel. Requests without
the secret get 401 and never reach the skill.
"""

import hmac
import json
import logging
from typing import Any, Protocol

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from catpoop.alexa_skill.body_limit import read_body
from catpoop.alexa_skill.endpoint import MAX_BODY

log = logging.getLogger(__name__)

PATH = "/alexa/smart-home"


class Skill(Protocol):
    """Answers a directive (`SmartHome`)."""

    def answer(self, request: dict[str, Any]) -> dict[str, Any]:
        """The response."""
        ...


router = APIRouter()


@router.post(PATH)
async def smart_home(request: Request) -> Response:
    """Answer a directive with `app.state.smart_home` when the bearer secret matches.

    Async like the Alexa endpoint, so it answers one request at a time on the same loop.
    """
    expected = f"Bearer {request.app.state.smart_home_secret}".encode()
    given = request.headers.get("authorization", "")
    if not hmac.compare_digest(given.encode(), expected):
        log.warning("Smart Home request without the right secret")
        return PlainTextResponse("unauthorized", 401)
    skill: Skill = request.app.state.smart_home
    body = await read_body(request, MAX_BODY)
    try:
        answer = skill.answer(json.loads(body))
    except Exception:
        log.exception("the Smart Home skill failed")
        return PlainTextResponse("error", 500)
    return JSONResponse(answer)
