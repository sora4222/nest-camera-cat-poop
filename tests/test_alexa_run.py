import json

import pytest
from cryptography.x509.verification import Store
from fake_amazon_certs import NOW, make_fake_amazon
from fake_clock import FakeClock
from fastapi.testclient import TestClient

from catpoop.alexa_skill.run import SKILL_ID_ENV, alexa_app
from catpoop.communications.switches import Switches
from catpoop.config import Config, ConfigError
from catpoop.domain import Event, Urgency
from catpoop.parts.memory_event_log import MemoryEventLog

SKILL_ID = "amzn1.ask.skill.test"
CERT_URL = "https://s3.amazonaws.com/echo.api/echo-api-cert.pem"


def config(enabled: bool = True) -> Config:
    return Config.model_validate(
        {
            "parts": dict.fromkeys(
                ["camera", "detector", "event_rules", "event_log", "presence", "communications"],
                "fake",
            ),
            "paths": {"private_data_store": "/data/store"},
            "household": {"cat": "Whiskers"},
            "alexa_skill": {"enabled": enabled, "port": 0},
        }
    )


class Certificates:
    def __init__(self, chain: bytes) -> None:
        self.chain = chain

    def fetch(self, url: str) -> bytes:
        return self.chain


def status_request() -> bytes:
    return json.dumps(
        {
            "version": "1.0",
            "context": {"System": {"application": {"applicationId": SKILL_ID}}},
            "request": {
                "type": "IntentRequest",
                "timestamp": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "intent": {"name": "StatusIntent", "slots": {}},
            },
        }
    ).encode()


def test_when_off_there_is_no_app():
    assert alexa_app(config(enabled=False), MemoryEventLog(), FakeClock(NOW), {}) is None


def test_when_on_it_needs_the_skill_id():
    with pytest.raises(ConfigError, match=SKILL_ID_ENV):
        alexa_app(config(), MemoryEventLog(), FakeClock(NOW), {})


def test_a_signed_status_request_is_answered_end_to_end(tmp_path):
    amazon = make_fake_amazon()
    event_log = MemoryEventLog()
    event_log.record(Event("poop", Urgency.NORMAL, NOW))
    body = status_request()
    app = alexa_app(
        config(),
        event_log,
        FakeClock(NOW),
        {SKILL_ID_ENV: SKILL_ID},
        certificates=Certificates(amazon.chain),
        trusted=Store([amazon.root]),
        switches=Switches(tmp_path / "switches.json"),
    )
    assert app is not None
    client = TestClient(app)
    headers = {"SignatureCertChainUrl": CERT_URL, "Signature-256": amazon.sign(body)}
    answer = client.post("/alexa", content=body, headers=headers)
    forged = client.post("/alexa", content=body.replace(b"Status", b"Statux"), headers=headers)
    other = client.get("/")
    docs = client.get("/docs")
    assert answer.status_code == 200
    assert answer.json()["response"]["outputSpeech"]["text"].startswith("Yes, there has been poop")
    assert forged.status_code == 400
    assert other.status_code == 404
    assert docs.status_code == 404
