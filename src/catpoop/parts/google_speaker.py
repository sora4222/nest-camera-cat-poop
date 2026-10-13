"""Speaker kind "google": a Google Home / Nest speaker saying speech made here with Piper.

The text never leaves the house: Piper makes a wav on the server, a small HTTP server on the
LAN address serves it, and the speaker (found by name) is told to play that URL. Every
"google" Speaker shares one loaded voice per model file and one server per address.
"""

from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

from catpoop.config import Config, ConfigError
from catpoop.interfaces import AudioHost, AudioPlayer, SpeechMaker
from catpoop.registry import DEFAULT, SPEAKER
from catpoop.speech.audio_server import AudioServer, lan_address
from catpoop.speech.cast_player import CastPlayer, find_cast
from catpoop.speech.piper_speech import load_piper


class GoogleSpeaker:
    """Says text by serving Piper speech to one Google speaker."""

    def __init__(self, name: str, speech: SpeechMaker, host: AudioHost, player: AudioPlayer):
        """A Speaker called `name` (the `[[speakers]]` name, not the device name)."""
        self.name = name
        self._speech = speech
        self._host = host
        self._player = player

    def say(self, text: str) -> None:
        """Make `text` into speech and have the speaker play it."""
        self._player.play(self._host.offer(self._speech.wav(text)))


@cache
def shared_speech(model: Path, lead_in_seconds: float) -> SpeechMaker:
    """One loaded Piper voice per model file."""
    try:
        return load_piper(model, lead_in_seconds)
    except ModuleNotFoundError as error:
        raise ConfigError(
            f"speaker kind 'google' needs the google extra ({error.name} is missing); "
            "run `make setup EXTRAS=google`"
        ) from None


@cache
def shared_host(host: str, port: int) -> AudioHost:
    """One audio server per address."""
    return AudioServer(host, port)


@DEFAULT.part(SPEAKER, "google")
def _create(config: Config, options: Mapping[str, Any]) -> GoogleSpeaker:
    where = f"speakers {options['name']!r}"
    device = options.get("device")
    if not device:
        raise ConfigError(f"{where}: device, the speaker's name in the Google Home app, is missing")
    if not options.get("voice"):
        raise ConfigError(f"{where}: voice, the Piper .onnx voice file, is missing")
    model = config.paths.private_data_store / Path(options["voice"])
    if not model.is_file():
        raise ConfigError(f"{where}: voice {model} not found")
    speech = shared_speech(model, float(options.get("lead_in_seconds", 0.5)))
    host = shared_host(options.get("serve_host") or lan_address(), options.get("serve_port", 8766))
    known_hosts = options.get("known_hosts")
    player = CastPlayer(
        device, lambda name: find_cast(name, known_hosts), volume=options.get("volume")
    )
    return GoogleSpeaker(options["name"], speech, host, player)
