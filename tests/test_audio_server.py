import ipaddress
from datetime import UTC, datetime

import httpx
import pytest
from fake_clock import FakeClock

from catpoop.speech import audio_server
from catpoop.speech.audio_server import AudioServer

START = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)


@pytest.fixture
def clock():
    return FakeClock(START)


@pytest.fixture
def server(clock):
    server = AudioServer("127.0.0.1", port=0, keep_seconds=60, clock=clock)
    yield server
    server.close()


def get(url: str) -> httpx.Response:
    return httpx.get(url, trust_env=False)


def test_serves_an_offered_wav_at_a_random_url(server):
    url = server.offer(b"RIFF....WAVE")
    assert url.startswith("http://127.0.0.1:")
    assert url.endswith(".wav")
    response = get(url)
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFF....WAVE"


def test_each_offer_gets_its_own_url(server):
    assert server.offer(b"a") != server.offer(b"b")


def test_unknown_paths_are_not_found(server):
    url = server.offer(b"a")
    assert get(url.rsplit("/", 1)[0] + "/nope.wav").status_code == 404


def test_clips_are_forgotten_after_keep_seconds(server, clock):
    old = server.offer(b"old")
    clock.advance(61)
    server.offer(b"new")
    assert get(old).status_code == 404


def test_close_without_an_offer_is_fine(clock):
    AudioServer("127.0.0.1", port=0, clock=clock).close()


def test_lan_address_follows_the_default_route_not_a_private_range(monkeypatch):
    probed: list[tuple[str, int]] = []

    class Probe:
        def __init__(self, *args) -> None: ...
        def __enter__(self):
            return self

        def __exit__(self, *args) -> None: ...
        def connect(self, target: tuple[str, int]) -> None:
            probed.append(target)

        def getsockname(self) -> tuple[str, int]:
            return ("192.0.2.5", 40000)

    monkeypatch.setattr(audio_server.socket, "socket", Probe)
    assert audio_server.lan_address() == "192.0.2.5"
    assert ipaddress.ip_address(probed[0][0]).is_global
