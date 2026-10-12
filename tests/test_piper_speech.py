import io
import wave
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from catpoop.speech.piper_speech import PiperSpeech, load_piper


@dataclass
class Chunk:
    audio_int16_bytes: bytes


class FakeVoice:
    config = SimpleNamespace(sample_rate=100)

    def __init__(self):
        self.said: list[str] = []

    def synthesize(self, text):
        self.said.append(text)
        return iter([Chunk(b"\x01\x00" * 3), Chunk(b"\x02\x00" * 2)])


def read(wav_bytes: bytes):
    with wave.open(io.BytesIO(wav_bytes)) as wav:
        return wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.readframes(1000)


def test_wav_holds_every_chunk_as_16_bit_mono():
    voice = FakeVoice()
    rate, channels, width, frames = read(PiperSpeech(voice, lead_in_seconds=0).wav("Hello"))
    assert voice.said == ["Hello"]
    assert (rate, channels, width) == (100, 1, 2)
    assert frames == b"\x01\x00" * 3 + b"\x02\x00" * 2


def test_wav_starts_with_silence_so_the_speaker_does_not_cut_the_start():
    _, _, _, frames = read(PiperSpeech(FakeVoice(), lead_in_seconds=0.1).wav("Hello"))
    assert frames.startswith(b"\x00\x00" * 10 + b"\x01\x00")


def test_load_piper_needs_the_model_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_piper(tmp_path / "missing.onnx")
