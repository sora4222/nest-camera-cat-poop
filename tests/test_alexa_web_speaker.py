import pytest

from catpoop.alexa_web import AlexaWeb
from catpoop.config import Config, ConfigError
from catpoop.parts.alexa_web_speaker import TOKEN_ENV, AlexaWebSpeaker
from catpoop.registry import SPEAKER, default_registry


class FakeWeb:
    def __init__(self) -> None:
        self.said: list[tuple[str, str]] = []

    def speak(self, device: str, text: str) -> None:
        self.said.append((device, text))


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


def create(options: dict):
    return default_registry().create(
        SPEAKER, "alexa_web", config(), {"kind": "alexa_web", **options}
    )


def test_say_speaks_on_the_device():
    web = FakeWeb()
    AlexaWebSpeaker("Kitchen", "Kitchen Echo", web).say("Poop in the litter box")
    assert web.said == [("Kitchen Echo", "Poop in the litter box")]


def test_registered_as_alexa_web_with_the_device_defaulting_to_the_name(monkeypatch):
    monkeypatch.setenv(TOKEN_ENV, "Atnr|x")
    part = create({"name": "Kitchen", "domain": "amazon.com.au", "locale": "en-AU"})
    assert isinstance(part, AlexaWebSpeaker)
    assert part.device == "Kitchen"
    assert isinstance(part.web, AlexaWeb)


def test_missing_token_is_a_config_error_naming_the_variable(monkeypatch):
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    with pytest.raises(ConfigError, match=TOKEN_ENV):
        create({"name": "Kitchen"})
