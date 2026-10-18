"""Integration: each example Alexa request goes to the real app and database.

The app is built as the watcher builds it (`alexa_app`) and called through FastAPI's
`TestClient`, with its Events in PostgreSQL (`postgres_url`, often a Testcontainer with a
random port, user and password) and real Do Not Disturb switches. Only Amazon and the clock
are fakes.
"""

import logging
from collections.abc import Iterator
from contextlib import closing
from datetime import timedelta
from pathlib import Path

import httpx
import psycopg
import pytest
from fake_amazon_certs import NOW, make_fake_amazon
from fastapi.testclient import TestClient
from postgres_server import empty_schema

from catpoop.database import upgrade
from catpoop.domain import Event, Urgency
from catpoop.parts.postgres_event_log import PostgresEventLog

REQUESTS = Path(__file__).parent / "alexa_requests"
SKILL_ID = "amzn1.ask.skill.00000000-0000-0000-0000-000000000000"
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


class Server:
    """The app and what it keeps: one Event log in the database, and the switches file."""

    def __init__(self, database: str, switches: Path) -> None:
        self.amazon, self.switches = make_fake_amazon(), switches
        self.db = psycopg.connect(database, autocommit=True)
        self.event_log = PostgresEventLog(database)
        self.http = TestClient(self.amazon.skill_app(self.event_log, switches, SKILL_ID))

    def reset(self, *events: Event) -> None:
        """Only `events` in the Event log, and every switch off."""
        self.db.execute("TRUNCATE events")
        for event in events:
            self.event_log.record(event)
        self.switches.unlink(missing_ok=True)

    def post(self, name: str) -> httpx.Response:
        body = (REQUESTS / f"{name}.json").read_bytes()
        return self.http.post("/alexa", content=body, headers=self.amazon.headers(body))

    def said(self, name: str) -> str:
        return self.post(name).json()["response"]["outputSpeech"]["text"]

    def close(self) -> None:
        self.http.close()
        self.event_log.close()
        self.db.close()


@pytest.fixture(scope="module")
def server(postgres_url, tmp_path_factory) -> Iterator[Server]:
    """The Alexa skill app, with its Event log in a new, upgraded schema."""
    switches = tmp_path_factory.mktemp("switches") / "switches.json"
    with empty_schema(postgres_url) as database:
        upgrade(database)
        with closing(Server(database, switches)) as server:
            yield server


@pytest.fixture(autouse=True)
def fresh(server: Server) -> None:
    """Each test starts with only the Poop from an hour ago, and every switch off."""
    server.reset(Event("poop", Urgency.NORMAL, POOP_AT))


@pytest.mark.parametrize("name", EXPECTED)
def test_each_command_gets_the_expected_answer(name, server, caplog):
    with caplog.at_level(logging.WARNING):
        response = server.post(name)
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


def test_quiet_poop_shows_in_the_status(server):
    server.post("quiet_poop")
    assert server.said("status").endswith("No poop news until 12 PM.")
    server.post("stop_quiet_poop")
    assert "No poop news" not in server.said("status")


def test_the_answer_to_how_long_quiets_visits(server):
    server.post("quiet_visits")
    server.post("duration")
    assert server.said("status").endswith("No news about visits or pee until 10:30 AM.")


def test_pee_announcements_off_shows_in_the_status(server):
    server.post("pee_announcements_off")
    assert server.said("status").endswith("Pee announcements are off.")
    server.post("pee_announcements_on")
    assert "Pee announcements" not in server.said("status")


def test_status_reads_the_poop_from_the_database(server):
    server.reset()
    assert server.said("status") == "No, there is no poop in the litter box."
