import json
import logging

import httpx
import pytest

from catpoop.config import Config, ConfigError
from catpoop.parts.voice_monkey_speaker import TOKEN_ENV, VoiceMonkeyError, VoiceMonkeySpeaker
from catpoop.registry import SPEAKER, default_registry

ANNOUNCE = "https://api-v3.voicemonkey.io/announce"
TOKEN = "secret-vm-token"


class VoiceMonkey:
    """A fake of the Voice Monkey announce endpoint."""

    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.requests: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status, json={"success": False, "error": "bad device"})
        return httpx.Response(200, json={"success": True})


def speaker(fake: VoiceMonkey, **options) -> VoiceMonkeySpeaker:
    http = httpx.Client(transport=httpx.MockTransport(fake.handle))
    return VoiceMonkeySpeaker(
        "Kitchen", options.pop("device", "kitchen-echo"), TOKEN, http, **options
    )


def config() -> Config:
    return Config.model_validate(
        {
            "parts": dict.fromkeys(
                ["camera", "detector", "event_rules", "event_log", "presence", "communications"],
                "x",
            ),
            "paths": {"private_data_store": "/data"},
        }
    )


def test_say_posts_the_text_to_the_device_with_the_token_as_bearer():
    fake = VoiceMonkey()
    speaker(fake).say("Poop in the litter box")
    [request] = fake.requests
    assert request.method == "POST"
    assert str(request.url) == ANNOUNCE
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    assert json.loads(request.content) == {
        "device": "kitchen-echo",
        "speech": "Poop in the litter box",
    }


def test_voice_and_chime_are_sent_when_set():
    fake = VoiceMonkey()
    speaker(fake, voice="Brian", chime="soundbank://x").say("hi")
    body = json.loads(fake.requests[0].content)
    assert body["voice"] == "Brian"
    assert body["chime"] == "soundbank://x"


def test_refused_announcement_raises_without_the_token():
    fake = VoiceMonkey(status=401)
    with pytest.raises(VoiceMonkeyError) as error:
        speaker(fake).say("hi")
    assert "401" in str(error.value)
    assert TOKEN not in str(error.value)
    assert TOKEN not in repr(error.value)


def test_success_false_in_the_answer_is_an_error():
    def refuse(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": False, "error": "unknown device"})

    http = httpx.Client(transport=httpx.MockTransport(refuse))
    with pytest.raises(VoiceMonkeyError, match="unknown device"):
        VoiceMonkeySpeaker("Kitchen", "kitchen-echo", TOKEN, http).say("hi")


def test_answer_that_is_not_json_is_fine_when_ok():
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="OK")))
    VoiceMonkeySpeaker("Kitchen", "kitchen-echo", TOKEN, http).say("hi")


def test_network_failure_raises_without_the_token():
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot connect {request.headers['authorization']}")

    http = httpx.Client(transport=httpx.MockTransport(fail))
    with pytest.raises(VoiceMonkeyError) as error:
        VoiceMonkeySpeaker("Kitchen", "kitchen-echo", TOKEN, http).say("hi")
    assert TOKEN not in str(error.value)
    assert error.value.__cause__ is None


def test_token_is_not_in_repr_or_logs(caplog):
    fake = VoiceMonkey()
    with caplog.at_level(logging.DEBUG):
        alexa = speaker(fake)
        alexa.say("hi")
    assert TOKEN not in repr(alexa)
    assert TOKEN not in caplog.text


def test_registered_as_voice_monkey_and_reads_the_token_from_the_environment(monkeypatch):
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    part = default_registry().create(
        SPEAKER,
        "voice_monkey",
        config(),
        {"name": "Kitchen", "kind": "voice_monkey", "device": "kitchen-echo"},
    )
    assert isinstance(part, VoiceMonkeySpeaker)
    assert part.name == "Kitchen"


def test_missing_token_is_a_config_error_naming_the_variable(monkeypatch):
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    with pytest.raises(ConfigError, match=TOKEN_ENV):
        default_registry().create(
            SPEAKER,
            "voice_monkey",
            config(),
            {"name": "Kitchen", "kind": "voice_monkey", "device": "k"},
        )


def test_missing_device_is_a_config_error(monkeypatch):
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    with pytest.raises(ConfigError, match="device"):
        default_registry().create(
            SPEAKER, "voice_monkey", config(), {"name": "Kitchen", "kind": "voice_monkey"}
        )
