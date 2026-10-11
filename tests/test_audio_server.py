import time
from datetime import UTC, datetime

import httpx
import pytest
from fake_clock import FakeClock

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


def test_speakers_offering_at_once_start_one_server(clock, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from catpoop.speech import audio_server as module

    built = []

    class SlowToBind(module.ThreadingHTTPServer):
        def __init__(self, *args, **kwargs):
            built.append(self)
            time.sleep(0.05)  # widen the gap between the check and the bind
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(module, "ThreadingHTTPServer", SlowToBind)
    server = AudioServer("127.0.0.1", port=0, clock=clock)
    together = Barrier(4)

    def offer(wav: bytes) -> str:
        together.wait()
        return server.offer(wav)

    try:
        with ThreadPoolExecutor(4) as pool:
            urls = list(pool.map(offer, [b"a", b"b", b"c", b"d"]))
        assert len(built) == 1
        assert [get(url).content for url in urls] == [b"a", b"b", b"c", b"d"]
    finally:
        server.close()
        for extra in built[1:]:
            extra.server_close()
