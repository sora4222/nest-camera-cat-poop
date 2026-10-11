"""Is a phone on the home network? Knock on a TCP port, then read the kernel's neighbour table.

Needs no root: a refused or accepted connection proves the phone is there, and a silent phone
that still answers ARP shows as REACHABLE in `ip neigh` (Linux, iproute2).
"""

import json
import socket
import subprocess
import time
from collections.abc import Callable

type Connect = Callable[[str, int, float], None]
"""Opens and closes a TCP connection to (address, port) within a timeout; raises OSError."""
type RunCommand = Callable[[list[str]], str]
"""Runs a command and returns its output; raises if it cannot."""

_ANSWERED = {"REACHABLE"}
_ASKING = {"DELAY", "PROBE", "INCOMPLETE"}  # the kernel is still waiting for the phone


def _connect(address: str, port: int, timeout: float) -> None:
    socket.create_connection((address, port), timeout=timeout).close()


def _run(command: list[str]) -> str:
    return subprocess.run(command, capture_output=True, text=True, check=True, timeout=5).stdout


class NeighbourTable:
    """`PhoneSeer` for phones on the same Wi-Fi as this machine."""

    def __init__(
        self,
        port: int = 62078,
        timeout_seconds: float = 1.0,
        wait_seconds: int = 6,
        connect: Connect = _connect,
        run: RunCommand = _run,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """`port` is knocked on to wake the phone (62078 is open on iPhones)."""
        self._port = port
        self._timeout = timeout_seconds
        self._wait_seconds = wait_seconds
        self._connect = connect
        self._run = run
        self._sleep = sleep

    def seen(self, address: str) -> bool:
        """Whether the phone at `address` answers now. Raises if `ip neigh` cannot be read."""
        try:
            self._connect(address, self._port, self._timeout)
            return True
        except ConnectionRefusedError:
            return True
        except OSError:
            pass  # no TCP answer; the phone may still have answered ARP
        for _ in range(self._wait_seconds):
            state = self._state(address)
            if state not in _ASKING:
                return state in _ANSWERED
            self._sleep(1.0)
        return False

    def _state(self, address: str) -> str | None:
        """The neighbour state of `address`, e.g. REACHABLE or STALE; None if not listed."""
        for entry in json.loads(self._run(["ip", "-j", "neigh", "show", address]) or "[]"):
            if entry.get("dst") == address:
                return next(iter(entry.get("state", [])), None)
        return None
