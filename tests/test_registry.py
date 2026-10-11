from collections.abc import Mapping
from typing import Any

import pytest

from catpoop.config import Config, ConfigError
from catpoop.domain import Presence
from catpoop.registry import (
    CAMERA,
    COMMUNICATIONS,
    DETECTOR,
    EVENT_LOG,
    EVENT_RULES,
    PRESENCE,
    SPEAKER,
    Registry,
    UnknownPart,
    build_parts,
)


class FakePresence:
    def __init__(self, presence: Presence) -> None:
        self.presence = presence

    def check(self, listener: str) -> Presence:
        return self.presence


class FakeSpeaker:
    def __init__(self, name: str) -> None:
        self.name = name
        self.said: list[str] = []

    def say(self, text: str) -> None:
        self.said.append(text)


def make_config(**changes: Any) -> Config:
    data: dict[str, Any] = {
        "parts": {
            "camera": "fake",
            "detector": "fake",
            "event_rules": "fake",
            "event_log": "fake",
            "presence": "fake",
            "communications": "fake",
        },
        "paths": {"private_data_store": "/data"},
    }
    data.update(changes)
    return Config.model_validate(data)


def fake_registry() -> Registry:
    registry = Registry()
    for slot in [CAMERA, DETECTOR, EVENT_RULES, EVENT_LOG, COMMUNICATIONS]:
        registry.add(slot, "fake", lambda config, options: object())
    registry.add(PRESENCE, "fake", lambda config, options: FakePresence(Presence.HOME))
    registry.add(SPEAKER, "fake", lambda config, options: FakeSpeaker(options["name"]))
    return registry


def test_create_uses_registered_factory_with_part_options():
    registry = Registry()
    seen: list[Mapping[str, Any]] = []

    def factory(config: Config, options: Mapping[str, Any]) -> FakePresence:
        seen.append(options)
        return FakePresence(Presence.AWAY)

    registry.add(PRESENCE, "wifi", factory)
    config = make_config(presence={"timeout_minutes": 10})
    part = registry.create(PRESENCE, "wifi", config, config.part_options("presence"))
    assert part.check("Partner") is Presence.AWAY
    assert seen == [{"timeout_minutes": 10}]


def test_unknown_name_lists_known_names():
    registry = Registry()
    registry.add(PRESENCE, "off", lambda config, options: FakePresence(Presence.UNKNOWN))
    with pytest.raises(UnknownPart, match=r"'wifi'.*off"):
        registry.create(PRESENCE, "wifi", make_config(), {})


def test_unknown_part_is_a_config_error():
    assert issubclass(UnknownPart, ConfigError)


def test_same_name_twice_is_refused():
    registry = Registry()
    registry.add(PRESENCE, "off", lambda config, options: FakePresence(Presence.UNKNOWN))
    with pytest.raises(ValueError, match="off"):
        registry.add(PRESENCE, "off", lambda config, options: FakePresence(Presence.UNKNOWN))


def test_decorator_registers_factory():
    registry = Registry()

    @registry.part(PRESENCE, "home")
    def _home(config: Config, options: Mapping[str, Any]) -> FakePresence:
        return FakePresence(Presence.HOME)

    assert registry.names(PRESENCE) == ["home"]


def test_build_parts_makes_every_part_and_one_speaker_per_entry():
    config = make_config(
        speakers=[{"name": "Kitchen", "kind": "fake"}, {"name": "Bedroom", "kind": "fake"}]
    )
    parts = build_parts(config, fake_registry())
    assert parts.presence.check("Partner") is Presence.HOME
    assert [speaker.name for speaker in parts.speakers] == ["Kitchen", "Bedroom"]


def test_build_parts_fails_on_unknown_speaker_kind():
    config = make_config(speakers=[{"name": "Kitchen", "kind": "alexa"}])
    with pytest.raises(UnknownPart, match="speaker"):
        build_parts(config, fake_registry())
