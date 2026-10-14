"""Integration: each example Alexa request goes over HTTP to the real app and database.

The app is built as the watcher builds it (`alexa_app`, `serve_in_background`) on a free
port, with its Events in PostgreSQL (`database_url`, often a Testcontainer with a random
port, user and password) and real Do Not Disturb switches. Only Amazon and the clock are
fakes.
"""

import logging
import socket
import time
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path

import httpx
import psycopg
import pytest
from cryptography.x509.verification import Store
from fake_amazon_certs import NOW, make_fake_amazon
from fake_clock import FakeClock
from postgres_server import empty_schema

from catpoop.alexa_skill.run import SKILL_ID_ENV, alexa_app, serve_in_background
from catpoop.communications.switches import Switches
from catpoop.config import Config
from catpoop.domain import Event, Urgency
from catpoop.parts.postgres_event_log import URL_ENV, PostgresEventLog
from catpoop.registry import EVENT_LOG, default_registry

REQUESTS = Path(__file__).parent / "alexa_requests"
SKILL_ID = "amzn1.ask.skill.00000000-0000-0000-0000-000000000000"
CERT_URL = "https://s3.amazonaws.com/echo.api/echo-api-cert.pem"
HELP = "You can ask"
POOP_AT = NOW - timedelta(hours=1)

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


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def config(port: int) -> Config:
    return Config.model_validate(
        {
            "parts": dict.fromkeys(
                ["camera", "detector", "event_rules", "presence", "communications"], "x"
            )
            | {"event_log": "postgres"},
            "paths": {"private_data_store": "/data/store"},
            "household": {"cat": "Whiskers"},
            "alexa_skill": {"enabled": True, "port": port},
        }
    )


def wait_until_served(url: str) -> None:
    for _ in range(200):
        try:
            httpx.get(url, trust_env=False)
            return
        except httpx.ConnectError:
            time.sleep(0.025)
    raise TimeoutError(url)


class Server:
    """The served app, and what it keeps: the database and the switches file."""

    def __init__(self, url: str, database: str, switches: Path) -> None:
        self.url, self.database, self.switches = url, database, switches

    def post(self, amazon, name: str) -> httpx.Response:
        body = (REQUESTS / f"{name}.json").read_bytes()
        headers = {"SignatureCertChainUrl": CERT_URL, "Signature-256": amazon.sign(body)}
        return httpx.post(self.url, content=body, headers=headers, trust_env=False)

    def said(self, amazon, name: str) -> str:
        return self.post(amazon, name).json()["response"]["outputSpeech"]["text"]


@pytest.fixture(scope="module")
def server(amazon, postgres_url, tmp_path_factory) -> Generator[Server]:
    """The Alexa skill app on a free port, its Event log made from config and the env."""
    for database in empty_schema(postgres_url):
        settings = config(free_port())
        with pytest.MonkeyPatch.context() as env:
            env.setenv(URL_ENV, database)
            event_log = default_registry().create(EVENT_LOG, "postgres", settings, {})
        assert isinstance(event_log, PostgresEventLog)
        switches = tmp_path_factory.mktemp("switches") / "switches.json"
        app = alexa_app(
            settings,
            event_log,
            FakeClock(NOW),
            {SKILL_ID_ENV: SKILL_ID},
            certificates=Certificates(amazon.chain),
            trusted=Store([amazon.root]),
            switches=Switches(switches),
        )
        assert app is not None
        serve_in_background(app, settings.alexa_skill)
        url = f"http://127.0.0.1:{settings.alexa_skill.port}/alexa"
        wait_until_served(url)
        yield Server(url, database, switches)
        event_log.close()


@pytest.fixture(autouse=True)
def fresh(server: Server) -> None:
    """Each test starts with only the Poop from an hour ago, and every switch off."""
    with psycopg.connect(server.database, autocommit=True) as db:
        db.execute("TRUNCATE events")
    PostgresEventLog(server.database).record(Event("poop", Urgency.NORMAL, POOP_AT))
    server.switches.unlink(missing_ok=True)


@pytest.mark.parametrize("name", EXPECTED)
def test_each_command_gets_the_expected_answer(name, server, amazon, caplog):
    with caplog.at_level(logging.WARNING):
        response = server.post(amazon, name)
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


def test_quiet_poop_shows_in_the_status(server, amazon):
    server.post(amazon, "quiet_poop")
    assert server.said(amazon, "status").endswith("No poop news until 12 PM.")
    server.post(amazon, "stop_quiet_poop")
    assert "No poop news" not in server.said(amazon, "status")


def test_the_answer_to_how_long_quiets_visits(server, amazon):
    server.post(amazon, "quiet_visits")
    server.post(amazon, "duration")
    assert server.said(amazon, "status").endswith("No news about visits or pee until 10:30 AM.")


def test_pee_announcements_off_shows_in_the_status(server, amazon):
    server.post(amazon, "pee_announcements_off")
    assert server.said(amazon, "status").endswith("Pee announcements are off.")
    server.post(amazon, "pee_announcements_on")
    assert "Pee announcements" not in server.said(amazon, "status")


def test_status_reads_the_poop_from_the_database(server, amazon):
    with psycopg.connect(server.database, autocommit=True) as db:
        db.execute("TRUNCATE events")
    assert server.said(amazon, "status") == "No, there is no poop in the litter box."
