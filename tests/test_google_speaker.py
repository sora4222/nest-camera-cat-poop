from typing import Any

import pytest

from catpoop.config import Config, ConfigError
from catpoop.parts import google_speaker
from catpoop.parts.google_speaker import GoogleSpeaker
from catpoop.registry import SPEAKER, default_registry


class FakeSpeech:
    def wav(self, text):
        return f"wav:{text}".encode()


class FakeHost:
    def __init__(self):
        self.offered: list[bytes] = []

    def offer(self, wav):
        self.offered.append(wav)
        return f"http://lan/{len(self.offered)}.wav"


class FakePlayer:
    def __init__(self):
        self.played: list[str] = []

    def play(self, url):
        self.played.append(url)


def test_says_text_by_serving_piper_speech_to_the_speaker():
    host, player = FakeHost(), FakePlayer()
    speaker = GoogleSpeaker("Kitchen", FakeSpeech(), host, player)
    speaker.say("Poop in the litter box")
    assert speaker.name == "Kitchen"
    assert host.offered == [b"wav:Poop in the litter box"]
    assert player.played == ["http://lan/1.wav"]


def config(tmp_path) -> Config:
    return Config.model_validate(
        {
            "parts": {
                "camera": "nest",
                "detector": "onnx",
                "event_rules": "log",
                "event_log": "memory",
                "presence": "off",
                "communications": "standard",
            },
            "paths": {"private_data_store": str(tmp_path)},
        }
    )


def options(**changes: Any) -> dict[str, Any]:
    return {
        "name": "Kitchen",
        "kind": "google",
        "device": "Kitchen speaker",
        "voice": "voices/en.onnx",
        "serve_host": "127.0.0.1",
        "serve_port": 0,
    } | changes


@pytest.fixture
def voice_file(tmp_path, monkeypatch):
    (tmp_path / "voices").mkdir()
    (tmp_path / "voices" / "en.onnx").write_bytes(b"")
    loaded: list = []

    def load(path, lead_in_seconds=0.5):
        loaded.append(path)
        return FakeSpeech()

    monkeypatch.setattr(google_speaker, "load_piper", load)
    google_speaker.shared_speech.cache_clear()
    google_speaker.shared_host.cache_clear()
    yield loaded
    google_speaker.shared_host.cache_clear()


def create(tmp_path, **changes):
    return default_registry().create(SPEAKER, "google", config(tmp_path), options(**changes))


def test_registered_as_speaker_kind_google():
    assert "google" in default_registry().names(SPEAKER)


def test_speakers_share_one_voice_and_one_server(tmp_path, voice_file):
    kitchen = create(tmp_path)
    lounge = create(tmp_path, name="Lounge", device="Lounge speaker")
    assert voice_file == [tmp_path / "voices" / "en.onnx"]
    assert kitchen._speech is lounge._speech
    assert kitchen._host is lounge._host


def test_device_is_needed(tmp_path, voice_file):
    with pytest.raises(ConfigError, match="device"):
        create(tmp_path, device=None)


def test_voice_is_needed(tmp_path, voice_file):
    with pytest.raises(ConfigError, match="voice"):
        create(tmp_path, voice=None)


def test_voice_file_must_exist(tmp_path, voice_file):
    with pytest.raises(ConfigError, match="not found"):
        create(tmp_path, voice="voices/missing.onnx")


def test_without_the_google_extra_says_how_to_install_it(tmp_path, voice_file, monkeypatch):
    def load(path, lead_in_seconds=0.5):
        raise ModuleNotFoundError("No module named 'piper'", name="piper")

    monkeypatch.setattr(google_speaker, "load_piper", load)
    with pytest.raises(ConfigError, match="EXTRAS=google"):
        create(tmp_path)
