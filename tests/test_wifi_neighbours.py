import errno
import json

import pytest

from catpoop.parts.wifi_neighbours import NeighbourTable

PHONE = "192.0.2.10"
NO_ANSWER = TimeoutError("timed out")


class FakeLan:
    """Answers the wake-up knock and `ip -j neigh show` with prepared results."""

    def __init__(self, knock: OSError | None = NO_ANSWER, states=()) -> None:
        self.knock = knock
        self.states = list(states)
        self.knocked: list[tuple[str, int, float]] = []
        self.commands: list[list[str]] = []
        self.slept: list[float] = []

    def connect(self, address: str, port: int, timeout: float) -> None:
        self.knocked.append((address, port, timeout))
        if self.knock is not None:
            raise self.knock

    def run(self, command: list[str]) -> str:
        self.commands.append(command)
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        if state is None:
            return "[]"
        return json.dumps([{"dst": PHONE, "dev": "wlan0", "state": [state]}])

    def table(self) -> NeighbourTable:
        return NeighbourTable(
            port=62078,
            timeout_seconds=1.0,
            connect=self.connect,
            run=self.run,
            sleep=self.slept.append,
        )


def test_a_phone_that_takes_the_connection_is_seen():
    lan = FakeLan(knock=None)
    assert lan.table().seen(PHONE)
    assert lan.knocked == [(PHONE, 62078, 1.0)]
    assert lan.commands == []


def test_a_phone_that_refuses_the_connection_is_seen():
    assert FakeLan(knock=ConnectionRefusedError()).table().seen(PHONE)


def test_a_silent_phone_that_answered_arp_is_seen():
    lan = FakeLan(states=["REACHABLE"])
    assert lan.table().seen(PHONE)
    assert lan.commands == [["ip", "-j", "neigh", "show", PHONE]]


@pytest.mark.parametrize("state", ["STALE", "FAILED", None])
def test_a_phone_not_answering_is_not_seen(state):
    assert not FakeLan(states=[state]).table().seen(PHONE)


def test_waits_while_the_kernel_is_still_asking_the_phone():
    lan = FakeLan(states=["DELAY", "PROBE", "REACHABLE"])
    assert lan.table().seen(PHONE)
    assert lan.slept == [1.0, 1.0]


def test_gives_up_waiting_after_a_few_seconds():
    lan = FakeLan(states=["INCOMPLETE"])
    assert not lan.table().seen(PHONE)
    assert sum(lan.slept) <= 6


def test_a_missing_ip_command_is_a_failure():
    def no_ip(command: list[str]) -> str:
        raise FileNotFoundError("ip")

    table = NeighbourTable(connect=FakeLan().connect, run=no_ip, sleep=lambda s: None)
    with pytest.raises(FileNotFoundError):
        table.seen(PHONE)


def test_reads_the_table_once_more_after_the_last_wait():
    lan = FakeLan(states=["INCOMPLETE"] * 6 + ["REACHABLE"])
    assert lan.table().seen(PHONE)
    assert sum(lan.slept) == 6


@pytest.mark.parametrize("code", [errno.ENETUNREACH, errno.ENETDOWN])
def test_a_down_network_is_a_failure_not_an_absent_phone(code):
    lan = FakeLan(knock=OSError(code, "network down"), states=[None])
    with pytest.raises(OSError):
        lan.table().seen(PHONE)
