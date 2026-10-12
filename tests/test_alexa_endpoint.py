import json
import logging

import pytest

from catpoop.alexa_skill.endpoint import AlexaEndpoint
from catpoop.alexa_skill.request_verifier import RequestRejected

GOOD = {"SignatureCertChainUrl": "url", "Signature-256": "ok"}


class Verifier:
    def __init__(self) -> None:
        self.seen: list[tuple[dict, bytes]] = []

    def verify(self, headers, body: bytes) -> dict:
        self.seen.append((dict(headers), body))
        if headers.get("Signature-256") != "ok":
            raise RequestRejected("bad signature")
        return json.loads(body)


class Skill:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.requests: list[dict] = []

    def answer(self, request: dict) -> dict:
        if self.fail:
            raise RuntimeError("boom")
        self.requests.append(request)
        return {"version": "1.0", "response": {"shouldEndSession": True}}


def test_a_verified_post_to_alexa_gets_the_skills_answer_as_json():
    verifier, skill = Verifier(), Skill()
    response = AlexaEndpoint(verifier, skill).handle("POST", "/alexa", GOOD, b'{"a": 1}')
    assert response.status == 200
    assert response.content_type == "application/json;charset=UTF-8"
    assert json.loads(response.body) == {"version": "1.0", "response": {"shouldEndSession": True}}
    assert verifier.seen == [(GOOD, b'{"a": 1}')]
    assert skill.requests == [{"a": 1}]


def test_a_request_that_fails_verification_is_400_and_never_reaches_the_skill(caplog):
    skill = Skill()
    endpoint = AlexaEndpoint(Verifier(), skill)
    with caplog.at_level(logging.WARNING):
        response = endpoint.handle("POST", "/alexa", {"Signature-256": "forged"}, b"{}")
    assert response.status == 400
    assert skill.requests == []
    assert "bad signature" in caplog.text


@pytest.mark.parametrize("path", ["/", "/alexa/", "/alexa/x", "/other", "/alexa?x=1", "//alexa"])
def test_every_other_path_is_404_and_not_verified(path):
    verifier = Verifier()
    response = AlexaEndpoint(verifier, Skill()).handle("POST", path, GOOD, b"{}")
    assert response.status == 404
    assert verifier.seen == []


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE", "HEAD"])
def test_only_post_is_allowed_on_alexa(method):
    verifier = Verifier()
    response = AlexaEndpoint(verifier, Skill()).handle(method, "/alexa", GOOD, b"{}")
    assert response.status == 405
    assert verifier.seen == []


def test_a_failing_skill_is_500_and_logged(caplog):
    endpoint = AlexaEndpoint(Verifier(), Skill(fail=True))
    with caplog.at_level(logging.ERROR):
        response = endpoint.handle("POST", "/alexa", GOOD, b"{}")
    assert response.status == 500
    assert "boom" in caplog.text
