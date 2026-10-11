from datetime import UTC, datetime, timedelta

from fake_clock import FakeClock

from catpoop.domain import Presence
from catpoop.parts.wifi_presence import WifiPresence

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
