import sys
import types

import pytest

from catpoop.speech.cast_player import CastPlayer, SpeakerNotFound, find_cast


class FakeMedia:
    def __init__(self, fail=False):
        self.played: list[tuple] = []
        self.fail = fail

    def play_media(self, url, content_type, **kwargs):
        if self.fail:
            raise ConnectionError("gone")
        self.played.append((url, content_type, kwargs.get("stream_type")))


class FakeCast:
    def __init__(self, fail=False):
        self.media_controller = FakeMedia(fail)
        self.volumes: list[float] = []

    def set_volume(self, volume):
        self.volumes.append(volume)


class FakeDiscover:
    def __init__(self, *casts):
        self.casts = list(casts)
        self.asked: list[str] = []
        self.found: list[FakeFound] = []

    def __call__(self, device):
        self.asked.append(device)
        if not self.casts:
            return None
        found = FakeFound(self.casts.pop(0))
        self.found.append(found)
        return found


class FakeFound:
    def __init__(self, cast):
        self.cast = cast
        self.closed = False

    def close(self):
        self.closed = True


def test_plays_the_url_as_buffered_wav_on_the_named_device():
    cast = FakeCast()
    discover = FakeDiscover(cast)
    CastPlayer("Kitchen speaker", discover).play("http://lan/a.wav")
    assert discover.asked == ["Kitchen speaker"]
    assert cast.media_controller.played == [("http://lan/a.wav", "audio/wav", "BUFFERED")]


def test_finds_the_device_once():
    discover = FakeDiscover(FakeCast())
    player = CastPlayer("Kitchen speaker", discover)
    player.play("http://lan/a.wav")
    player.play("http://lan/b.wav")
    assert discover.asked == ["Kitchen speaker"]


def test_device_not_found():
    with pytest.raises(SpeakerNotFound, match="Kitchen speaker"):
        CastPlayer("Kitchen speaker", FakeDiscover()).play("http://lan/a.wav")


def test_finds_the_device_again_after_a_failure():
    discover = FakeDiscover(FakeCast(fail=True), FakeCast())
    player = CastPlayer("Kitchen speaker", discover)
    with pytest.raises(ConnectionError):
        player.play("http://lan/a.wav")
    player.play("http://lan/a.wav")
    assert len(discover.asked) == 2


def test_sets_the_volume_when_given():
    cast = FakeCast()
    CastPlayer("Kitchen speaker", FakeDiscover(cast), volume=0.6).play("http://lan/a.wav")
    assert cast.volumes == [0.6]


def test_closes_the_old_connection_when_the_cast_is_replaced():
    discover = FakeDiscover(FakeCast(fail=True), FakeCast())
    player = CastPlayer("Kitchen speaker", discover)
    with pytest.raises(ConnectionError):
        player.play("http://lan/a.wav")
    assert discover.found[0].closed
    player.play("http://lan/a.wav")
    assert not discover.found[1].closed


def test_close_ends_the_kept_connection():
    discover = FakeDiscover(FakeCast())
    player = CastPlayer("Kitchen speaker", discover)
    player.play("http://lan/a.wav")
    player.close()
    assert discover.found[0].closed


class FakeBrowser:
    def __init__(self, log):
        self.log = log

    def stop_discovery(self):
        self.log.append("stop discovery")


class FakeChromecast:
    def __init__(self, log):
        self.log = log

    def wait(self, timeout=None):
        self.log.append("wait")

    def disconnect(self, timeout=None):
        self.log.append("disconnect")


@pytest.fixture
def fake_pychromecast(monkeypatch):
    log: list[str] = []
    found: list = []
    module = types.SimpleNamespace(
        get_listed_chromecasts=lambda **kwargs: (list(found), FakeBrowser(log))
    )
    monkeypatch.setitem(sys.modules, "pychromecast", module)
    return log, found


def test_discovery_keeps_running_while_the_cast_is_in_use(fake_pychromecast):
    log, found = fake_pychromecast
    found.append(FakeChromecast(log))
    result = find_cast("Kitchen speaker")
    assert result is not None
    assert log == ["wait"]
    result.close()
    assert log == ["wait", "disconnect", "stop discovery"]


def test_discovery_stops_when_no_cast_is_found(fake_pychromecast):
    log, _ = fake_pychromecast
    assert find_cast("Kitchen speaker") is None
    assert log == ["stop discovery"]
