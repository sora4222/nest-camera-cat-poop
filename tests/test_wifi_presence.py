import time
from datetime import UTC, datetime, timedelta

import pytest
from fake_clock import FakeClock

from catpoop.config import Config, ConfigError
from catpoop.domain import Presence
from catpoop.parts import wifi_presence
from catpoop.parts.wifi_presence import WifiPresence, build_wifi_presence
from catpoop.registry import PRESENCE, default_registry

START = datetime(2026, 6, 1, 20, 0, tzinfo=UTC)
PHONE = "192.0.2.10"


class FakeNetwork:
    """Phones on the Wi-Fi by address; `broken` makes every look fail."""

    def __init__(self) -> None:
        self.on_wifi: set[str] = set()
        self.broken = False
        self.looked: list[str] = []

    def seen(self, address: str) -> bool:
        self.looked.append(address)
        if self.broken:
            raise OSError("no neighbour table")
        return address in self.on_wifi


def presence(network: FakeNetwork, clock: FakeClock, phones=None) -> WifiPresence:
    return WifiPresence(phones or {"Partner": PHONE}, network, clock, timedelta(minutes=10))


def test_unknown_before_the_first_look():
    assert presence(FakeNetwork(), FakeClock(START)).check("Partner") is Presence.UNKNOWN


def test_home_when_the_phone_is_seen():
    network = FakeNetwork()
    network.on_wifi.add(PHONE)
    wifi = presence(network, FakeClock(START))
    wifi.look()
    assert network.looked == [PHONE]
    assert wifi.check("Partner") is Presence.HOME


def test_away_when_the_phone_was_never_seen():
    wifi = presence(FakeNetwork(), FakeClock(START))
    wifi.look()
    assert wifi.check("Partner") is Presence.AWAY


def test_still_home_while_a_sleeping_phone_was_seen_recently():
    network, clock = FakeNetwork(), FakeClock(START)
    network.on_wifi.add(PHONE)
    wifi = presence(network, clock)
    wifi.look()
    network.on_wifi.clear()
    clock.advance(9 * 60)
    wifi.look()
    assert wifi.check("Partner") is Presence.HOME
    clock.advance(60)
    wifi.look()
    assert wifi.check("Partner") is Presence.AWAY


def test_unknown_for_everyone_while_the_look_fails():
    network, clock = FakeNetwork(), FakeClock(START)
    network.on_wifi.add(PHONE)
    wifi = presence(network, clock, {"Partner": PHONE, "Guest": "192.0.2.11"})
    wifi.look()
    network.broken = True
    wifi.look()
    assert wifi.check("Partner") is Presence.UNKNOWN
    assert wifi.check("Guest") is Presence.UNKNOWN
    network.broken = False
    wifi.look()
    assert wifi.check("Partner") is Presence.HOME


def test_unknown_for_a_listener_without_a_phone():
    wifi = presence(FakeNetwork(), FakeClock(START))
    wifi.look()
    assert wifi.check("Someone else") is Presence.UNKNOWN


def wait_for(done) -> None:
    deadline = time.monotonic() + 5
    while not done() and time.monotonic() < deadline:
        time.sleep(0.01)


def test_keeps_looking_in_the_background_until_closed():
    network = FakeNetwork()
    network.on_wifi.add(PHONE)
    wifi = presence(network, FakeClock(START))
    wifi.start(every_seconds=0.01)
    wait_for(lambda: len(network.looked) >= 2)
    wifi.close()
    assert len(network.looked) >= 2
    assert wifi.check("Partner") is Presence.HOME


def config(listeners) -> Config:
    return Config.model_validate(
        {
            "parts": {
                "camera": "nest",
                "detector": "onnx",
                "event_rules": "standard",
                "event_log": "memory",
                "presence": "wifi",
                "communications": "standard",
            },
            "paths": {"private_data_store": "/nowhere"},
            "listeners": listeners,
        }
    )


def test_built_from_listener_phone_addresses_and_presence_options():
    listeners = [{"name": "Partner", "phone_ip": PHONE}, {"name": "Guest"}]
    network, clock = FakeNetwork(), FakeClock(START)
    network.on_wifi.add(PHONE)
    wifi = build_wifi_presence(config(listeners), {"away_after_minutes": 2}, network, clock)
    wifi.look()
    assert network.looked == [PHONE]
    clock.advance(119)
    assert wifi.check("Partner") is Presence.HOME
    clock.advance(1)
    assert wifi.check("Partner") is Presence.AWAY
    assert wifi.check("Guest") is Presence.UNKNOWN


def test_away_after_ten_minutes_by_default():
    network, clock = FakeNetwork(), FakeClock(START)
    network.on_wifi.add(PHONE)
    wifi = build_wifi_presence(config([{"name": "P", "phone_ip": PHONE}]), {}, network, clock)
    wifi.look()
    clock.advance(10 * 60 - 1)
    assert wifi.check("P") is Presence.HOME
    clock.advance(1)
    assert wifi.check("P") is Presence.AWAY


@pytest.mark.parametrize(
    ("listeners", "options", "problem"),
    [
        ([{"name": "P", "phone_ip": "not an address"}], {}, "listeners P: phone_ip"),
        ([{"name": "P", "phone_ip": 1234}], {}, "listeners P: phone_ip"),
        ([{"name": "P", "phone_ip": True}], {}, "listeners P: phone_ip"),
        ([{"name": "P", "phone_ip": PHONE}], {"away_after_minutes": 0}, "presence.away_after"),
        ([{"name": "P", "phone_ip": PHONE}], {"away_after": 5}, "presence.away_after"),
    ],
)
def test_wrong_settings_are_config_errors(listeners, options, problem):
    with pytest.raises(ConfigError, match=problem):
        build_wifi_presence(config(listeners), options, FakeNetwork(), FakeClock(START))


def test_registered_as_wifi_and_starts_looking(monkeypatch):
    network = FakeNetwork()
    monkeypatch.setattr(wifi_presence, "NeighbourTable", lambda **options: network)
    wifi = default_registry().create(
        PRESENCE, "wifi", config([{"name": "P", "phone_ip": PHONE}]), {"look_seconds": 0.01}
    )
    wait_for(lambda: bool(network.looked))
    assert isinstance(wifi, WifiPresence)
    wifi.close()
    assert network.looked
