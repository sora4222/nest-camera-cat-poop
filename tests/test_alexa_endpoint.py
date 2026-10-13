import json
import logging
import threading
import time

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from catpoop.alexa_skill.endpoint import MAX_BODY, alexa_router
from catpoop.alexa_skill.request_verifier import RequestRejected
from catpoop.alexa_skill.server import serving

GOOD = {"SignatureCertChainUrl": "url", "Signature-256": "ok"}


class Verifier:
    def __init__(self) -> None:
        self.seen: list[tuple[dict, bytes]] = []

    def verify(self, headers, body: bytes) -> dict:
        self.seen.append(({k.lower(): v for k, v in headers.items()}, body))
        if headers.get("Signature-256") != "ok":
            raise RequestRejected("bad signature")
        return json.loads(body)


class Skill:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.requests: list[dict] = []

    def respond(self, request: dict) -> dict:
        if self.fail:
            raise RuntimeError("boom")
        self.requests.append(request)
        return {"version": "1.0", "response": {"shouldEndSession": True}}


def client(verifier: Verifier, skill: Skill) -> TestClient:
    app = FastAPI()
    app.include_router(alexa_router(verifier, skill))
    return TestClient(app)


def test_a_verified_post_to_alexa_gets_the_skills_answer_as_json():
    verifier, skill = Verifier(), Skill()
    response = client(verifier, skill).post("/alexa", content=b'{"a": 1}', headers=GOOD)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json;charset=UTF-8"
    assert response.json() == {"version": "1.0", "response": {"shouldEndSession": True}}
    [(headers, body)] = verifier.seen
    assert (headers["signature-256"], body) == ("ok", b'{"a": 1}')
    assert skill.requests == [{"a": 1}]


def test_a_request_that_fails_verification_is_400_and_never_reaches_the_skill(caplog):
    skill = Skill()
    with caplog.at_level(logging.WARNING):
        response = client(Verifier(), skill).post(
            "/alexa", content=b"{}", headers={"Signature-256": "forged"}
        )
    assert response.status_code == 400
    assert skill.requests == []
    assert "bad signature" in caplog.text


@pytest.mark.parametrize("path", ["/", "/alexa/x", "/other"])
def test_every_other_path_is_404_and_not_verified(path):
    verifier = Verifier()
    response = client(verifier, Skill()).post(path, content=b"{}", headers=GOOD)
    assert response.status_code == 404
    assert verifier.seen == []


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_only_post_is_allowed_on_alexa(method):
    verifier = Verifier()
    response = client(verifier, Skill()).request(method, "/alexa", content=b"{}", headers=GOOD)
    assert response.status_code == 405
    assert verifier.seen == []


def test_a_body_over_the_limit_is_413_and_not_verified():
    verifier = Verifier()
    response = client(verifier, Skill()).post("/alexa", content=b"x" * (MAX_BODY + 1))
    assert response.status_code == 413
    assert verifier.seen == []


def test_a_failing_skill_is_500_and_logged(caplog):
    with caplog.at_level(logging.ERROR):
        response = client(Verifier(), Skill(fail=True)).post("/alexa", content=b"{}", headers=GOOD)
    assert response.status_code == 500
    assert "boom" in caplog.text


class SlowSkill(Skill):
    def __init__(self) -> None:
        super().__init__()
        self.inside = self.most = 0

    def respond(self, request: dict) -> dict:
        self.inside += 1
        self.most = max(self.most, self.inside)
        time.sleep(0.05)
        self.inside -= 1
        return super().respond(request)


def test_the_skill_answers_one_request_at_a_time():
    skill = SlowSkill()
    app = FastAPI()
    app.include_router(alexa_router(Verifier(), skill))
    with serving(app, "127.0.0.1", 0) as (host, port):
        url = f"http://{host}:{port}/alexa"
        kwargs = {"content": b"{}", "headers": GOOD, "trust_env": False}
        posts = [threading.Thread(target=httpx.post, args=(url,), kwargs=kwargs) for _ in range(3)]
        for post in posts:
            post.start()
        for post in posts:
            post.join()
    assert len(skill.requests) == 3
    assert skill.most == 1
