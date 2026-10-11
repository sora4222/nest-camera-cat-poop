"""Make speech on this machine with a Piper voice, so no text leaves the house.

`piper` comes from the `google` extra and is imported only when a voice is loaded.
"""

import io
import wave
from pathlib import Path
from typing import Any


class PiperSpeech:
    """Text to a 16-bit mono wav with a loaded Piper voice."""

    def __init__(self, voice: Any, lead_in_seconds: float = 0.5) -> None:
        """`voice` is a `piper.PiperVoice`. `lead_in_seconds` of silence come first, as speakers
        often miss the start of a clip while they wake up."""
        self._voice = voice
        self._lead_in = lead_in_seconds

    def wav(self, text: str) -> bytes:
        """`text` spoken, as the bytes of a wav file."""
        rate = self._voice.config.sample_rate
        out = io.BytesIO()
        with wave.open(out, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            wav.writeframes(b"\x00\x00" * round(rate * self._lead_in))
            for chunk in self._voice.synthesize(text):
                wav.writeframes(chunk.audio_int16_bytes)
        return out.getvalue()


def load_piper(model: Path, lead_in_seconds: float = 0.5) -> PiperSpeech:
    """Load the Piper voice `model` (.onnx, with its .onnx.json next to it) on the CPU."""
    if not model.is_file():
        raise FileNotFoundError(f"Piper voice {model} not found")
    from piper import PiperVoice

    return PiperSpeech(PiperVoice.load(model), lead_in_seconds)
