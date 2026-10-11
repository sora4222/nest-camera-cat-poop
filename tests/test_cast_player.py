import pytest

from catpoop.speech.cast_player import CastPlayer, SpeakerNotFound


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

    def __call__(self, device):
        self.asked.append(device)
        return self.casts.pop(0) if self.casts else None


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
