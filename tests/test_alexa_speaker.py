import pytest

from catpoop.config import Config, ConfigError, Household
from catpoop.parts.alexa_speaker import AlexaSpeaker, NoSensor
from catpoop.registry import SPEAKER, default_registry

TEMPLATES = {"poop": "{cat} left poop.", "dog_at_poop": "{dog} is at the poop!"}


class Gateway:
    def __init__(self) -> None:
        self.fired: list[str] = []

    def trigger(self, endpoint_id: str) -> None:
        self.fired.append(endpoint_id)


def speaker(gateway: Gateway) -> AlexaSpeaker:
    return AlexaSpeaker("Echo", TEMPLATES, Household(cat="Whiskers", dog="Rex"), gateway)


def test_say_fires_the_sensor_of_the_message_kind():
    gateway = Gateway()
    speaker(gateway).say("Rex is at the poop!")
    assert gateway.fired == ["catpoop-dog-at-poop"]


def test_text_from_no_template_raises():
    with pytest.raises(NoSensor):
        speaker(Gateway()).say("hello")


def config() -> Config:
    return Config.model_validate(
        {
            "parts": dict.fromkeys(
                ["camera", "detector", "event_rules", "event_log", "presence", "communications"],
                "x",
            ),
            "paths": {"private_data_store": "/data"},
            "messages": TEMPLATES,
        }
    )


def test_registered_as_alexa(monkeypatch):
    monkeypatch.setenv("CATPOOP_ALEXA_CLIENT_ID", "id")
    monkeypatch.setenv("CATPOOP_ALEXA_CLIENT_SECRET", "secret")
    options = {"name": "Echo", "kind": "alexa", "region": "FE"}
    part = default_registry().create(SPEAKER, "alexa", config(), options)
    assert isinstance(part, AlexaSpeaker)


def test_unknown_region_is_a_config_error():
    options = {"name": "Echo", "kind": "alexa", "region": "AU"}
    with pytest.raises(ConfigError, match="region"):
        default_registry().create(SPEAKER, "alexa", config(), options)
