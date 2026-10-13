"""One example Alexa request per command, signed and sent through the real endpoint."""

import json
import logging
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from cryptography.x509.verification import Store
from fake_amazon_certs import NOW, make_fake_amazon
from fake_clock import FakeClock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from catpoop.alexa_skill.endpoint import router
from catpoop.alexa_skill.request_verifier import RequestVerifier
from catpoop.alexa_skill.skill import AlexaSkill
from catpoop.communications.switches import Switches
from catpoop.domain import Event, Urgency
from catpoop.parts.memory_event_log import MemoryEventLog

REQUESTS = Path(__file__).parent / "alexa_requests"
MODEL = Path(__file__).parents[1] / "alexa" / "interactionModels" / "custom" / "en-US.json"
SKILL_ID = "amzn1.ask.skill.00000000-0000-0000-0000-000000000000"
CERT_URL = "https://s3.amazonaws.com/echo.api/echo-api-cert.pem"
HELP = "You can ask"

EXPECTED = {  # request file -> (what Alexa says, or None for no speech; does the session end)
    "launch": ("Litter box here. You can ask", False),
    "status": ("Yes, there has been poop in the litter box since 9 AM.", True),
    "quiet_poop": ("OK, no poop news until 12 PM.", True),
    "quiet_visits": ("For how long should I give no news about visits or pee?", False),
    "duration": ("OK, no news about visits or pee until 10:30 AM.", True),
    "stop_quiet_poop": ("I wasn't being quiet about poop.", True),
    "stop_quiet_visits": ("I wasn't being quiet about visits or pee.", True),
    "pee_announcements_on": ("OK, I'll announce pee again.", True),
    "pee_announcements_off": ("OK, I won't announce pee.", True),
    "help": (HELP, False),
    "stop": ("Bye.", True),
    "cancel": ("Bye.", True),
    "fallback": (HELP, False),
    "navigate_home": (HELP, False),
    "session_ended": (None, None),
}


class Certificates:
    def __init__(self, chain: bytes) -> None:
        self.chain = chain

    def fetch(self, url: str) -> bytes:
        return self.chain


@pytest.fixture(scope="module")
def amazon():
    return make_fake_amazon()


def client(amazon, tmp_path: Path) -> TestClient:
    clock = FakeClock(NOW)
    event_log = MemoryEventLog()
    event_log.record(Event("poop", Urgency.NORMAL, NOW - timedelta(hours=1)))
    switches = Switches(tmp_path / "switches.json")
    app = FastAPI()
    app.state.verifier = RequestVerifier(
        SKILL_ID, Certificates(amazon.chain), clock, Store([amazon.root])
    )
    app.state.skill = AlexaSkill(switches, event_log, clock, ZoneInfo("UTC"), cat="Whiskers")
    app.include_router(router)
    return TestClient(app)


@pytest.mark.parametrize("name", EXPECTED)
def test_each_command_gets_the_expected_answer(name, amazon, tmp_path, caplog):
    body = (REQUESTS / f"{name}.json").read_bytes()
    headers = {"SignatureCertChainUrl": CERT_URL, "Signature-256": amazon.sign(body)}
    with caplog.at_level(logging.WARNING):
        response = client(amazon, tmp_path).post("/alexa", content=body, headers=headers)
    assert response.status_code == 200
    assert caplog.records == []
    answer = response.json()
    assert answer["version"] == "1.0"
    said, ends = EXPECTED[name]
    if said is None:
        assert answer["response"] == {}
        return
    assert answer["response"]["outputSpeech"]["text"].startswith(said)
    assert answer["response"]["shouldEndSession"] is ends


def test_every_command_in_the_interaction_model_has_an_example_request():
    model = json.loads(MODEL.read_text())
    commands = {intent["name"] for intent in model["interactionModel"]["languageModel"]["intents"]}
    examples = {
        json.loads((REQUESTS / f"{name}.json").read_text())["request"].get("intent", {}).get("name")
        for name in EXPECTED
    }
    assert commands <= examples
