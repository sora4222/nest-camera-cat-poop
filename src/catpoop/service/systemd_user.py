"""The real ServiceManager: `systemctl --user`. Tests pass a fake runner instead."""

import subprocess
from collections.abc import Callable, Sequence

from catpoop.service.settings import ServiceSetupError

Runner = Callable[[Sequence[str]], None]


def _run(argv: Sequence[str]) -> None:
    subprocess.run(argv, check=True)


class SystemdUser:
    """Runs `systemctl --user ...`; any failure becomes a ServiceSetupError."""

    def __init__(self, runner: Runner = _run) -> None:
        """Use `runner` to run each command (default: subprocess)."""
        self._runner = runner

    def reload(self) -> None:
        """`systemctl --user daemon-reload`."""
        self._systemctl("daemon-reload")

    def enable_now(self, unit: str) -> None:
        """`systemctl --user enable --now <unit>`."""
        self._systemctl("enable", "--now", unit)

    def disable_now(self, unit: str) -> None:
        """`systemctl --user disable --now <unit>`."""
        self._systemctl("disable", "--now", unit)

    def _systemctl(self, *args: str) -> None:
        argv = ["systemctl", "--user", *args]
        try:
            self._runner(argv)
        except FileNotFoundError as error:
            raise ServiceSetupError("systemctl not found; this needs Linux with systemd") from error
        except subprocess.CalledProcessError as error:
            raise ServiceSetupError(
                f"`{' '.join(argv)}` failed (exit {error.returncode})"
            ) from error
