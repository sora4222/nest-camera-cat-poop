import json
import socket

import httpx
import pytest
from cryptography.x509.verification import Store
from fake_amazon_certs import NOW, make_fake_amazon
from fake_clock import FakeClock

from catpoop.alexa_skill.run import SKILL_ID_ENV, alexa_skill_running
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


def test_when_off_nothing_is_served():
    with alexa_skill_running(config(enabled=False), MemoryEventLog(), FakeClock(NOW), {}) as url:
        assert url is None


def test_when_on_it_needs_the_skill_id():
    with pytest.raises(ConfigError, match=SKILL_ID_ENV):
        with alexa_skill_running(config(), MemoryEventLog(), FakeClock(NOW), {}):
            pass


def test_a_signed_status_request_is_answered_end_to_end(tmp_path):
    amazon = make_fake_amazon()
    event_log = MemoryEventLog()
    event_log.record(Event("poop", Urgency.NORMAL, NOW))
    body = status_request()
    with alexa_skill_running(
        config(),
        event_log,
        FakeClock(NOW),
        {SKILL_ID_ENV: SKILL_ID},
        certificates=Certificates(amazon.chain),
        trusted=Store([amazon.root]),
        switches=Switches(tmp_path / "switches.json"),
    ) as url:
        assert url is not None and url.endswith("/alexa")
        with httpx.Client(trust_env=False) as client:
            headers = {"SignatureCertChainUrl": CERT_URL, "Signature-256": amazon.sign(body)}
            answer = client.post(url, content=body, headers=headers)
            forged = client.post(url, content=body.replace(b"Status", b"Statux"), headers=headers)
            other = client.get(url.removesuffix("/alexa") + "/")
            docs = client.get(url.removesuffix("/alexa") + "/docs")
    assert answer.status_code == 200
    assert answer.json()["response"]["outputSpeech"]["text"].startswith("Yes, there has been poop")
    assert forged.status_code == 400
    assert other.status_code == 404
    assert docs.status_code == 404


def test_a_port_in_use_is_a_config_error():
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        busy = config().model_copy(
            update={"alexa_skill": config().alexa_skill.model_copy(update={"port": port})}
        )
        with pytest.raises(ConfigError, match="cannot listen"):
            with alexa_skill_running(busy, MemoryEventLog(), FakeClock(NOW), {SKILL_ID_ENV: "x"}):
                pass
