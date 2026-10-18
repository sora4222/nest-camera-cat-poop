import json

import httpx
import pytest
from fake_amazon_certs import NOW, make_fake_amazon, skill_config
from fake_clock import FakeClock
from fastapi.testclient import TestClient

from catpoop.alexa_skill.run import SKILL_ID_ENV, alexa_app
from catpoop.alexa_smart_home.grants import Grants
from catpoop.config import ConfigError
from catpoop.domain import Event, Urgency
from catpoop.parts.memory_event_log import MemoryEventLog

SKILL_ID = "amzn1.ask.skill.test"


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
    assert alexa_app(skill_config(enabled=False), MemoryEventLog(), FakeClock(NOW), {}) is None


def test_when_on_it_needs_the_skill_id():
    with pytest.raises(ConfigError, match=SKILL_ID_ENV):
        alexa_app(skill_config(), MemoryEventLog(), FakeClock(NOW), {})


def test_a_signed_status_request_is_answered_end_to_end(tmp_path):
    amazon = make_fake_amazon()
    event_log = MemoryEventLog()
    event_log.record(Event("poop", Urgency.NORMAL, NOW))
    body = status_request()
    client = TestClient(amazon.skill_app(event_log, tmp_path / "switches.json", SKILL_ID))
    headers = amazon.headers(body)
    answer = client.post("/alexa", content=body, headers=headers)
    forged = client.post("/alexa", content=body.replace(b"Status", b"Statux"), headers=headers)
    other = client.get("/")
    docs = client.get("/docs")
    assert answer.status_code == 200
    assert answer.json()["response"]["outputSpeech"]["text"].startswith("Yes, there has been poop")
    assert forged.status_code == 400
    assert other.status_code == 404
    assert docs.status_code == 404


def test_smart_home_needs_its_secret():
    on = skill_config().model_copy(
        update={"alexa_skill": skill_config().alexa_skill.model_copy(update={"smart_home": True})}
    )
    with pytest.raises(ConfigError, match="CATPOOP_ALEXA_SMART_HOME_SECRET"):
        alexa_app(on, MemoryEventLog(), FakeClock(NOW), {SKILL_ID_ENV: "x"})


def test_smart_home_is_served_next_to_the_skill(tmp_path):
    on = skill_config().model_copy(
        update={
            "alexa_skill": skill_config().alexa_skill.model_copy(update={"smart_home": True}),
            "messages": {"poop": "{cat} pooped."},
        }
    )
    env = {SKILL_ID_ENV: "x", "CATPOOP_ALEXA_SMART_HOME_SECRET": "s3cret"}
    grants = Grants("id", "secret", tmp_path / "grant.json", FakeClock(NOW), httpx.Client())
    discover = {"directive": {"header": {"namespace": "Alexa.Discovery", "name": "Discover"}}}
    app = alexa_app(on, MemoryEventLog(), FakeClock(NOW), env, grants=grants)
    assert app is not None
    answer = TestClient(app).post(
        "/alexa/smart-home", json=discover, headers={"Authorization": "Bearer s3cret"}
    )
    [sensor] = answer.json()["event"]["payload"]["endpoints"]
    assert sensor["friendlyName"] == "Litter box poop"
