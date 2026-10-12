"""`catpoop service install|uninstall|show` (`make install`, `make uninstall`)."""

import argparse
import getpass
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from catpoop.interfaces import ServiceManager
from catpoop.service import installer
from catpoop.service.settings import ServiceSetupError, find_settings
from catpoop.service.systemd_user import SystemdUser
from catpoop.service.unit_file import UNIT_NAME, render_unit

ACTIONS = ("install", "uninstall", "show")
_LOGS = "journalctl --user -u catpoop -f"


@dataclass(frozen=True)
class Places:
    """Where the unit, the service's secrets and systemd's linger flags are."""

    unit_folder: Path
    secrets_file: Path
    linger_folder: Path = Path("/var/lib/systemd/linger")

    @classmethod
    def default(cls) -> "Places":
        """The user's own folders."""
        return cls(installer.unit_folder(), installer.secrets_file())


def add_command(commands: Any) -> None:
    """Add `service` to the CLI's subparsers."""
    service = commands.add_parser("service", help="run the watcher as a systemd user service")
    service.add_argument("action", choices=ACTIONS)
    service.add_argument("--checkout", type=Path, default=Path.cwd(), help="default: here")
    service.add_argument("--runtime", default="cpu", choices=["cpu", "amd", "nvidia"])
    service.add_argument(
        "--extra", dest="extras", action="append", default=[], help="more uv extras, e.g. google"
    )


def run(args: argparse.Namespace) -> int:
    """Run `catpoop service <action>` with the real systemd."""
    return run_service(
        args.action, args.checkout, args.runtime, args.extras, Places.default(), SystemdUser()
    )


def run_service(
    action: str,
    checkout: Path,
    runtime: str,
    extras: list[str],
    places: Places,
    manager: ServiceManager,
    which: Callable[[str], str | None] = shutil.which,
    user: str | None = None,
) -> int:
    """Install, uninstall or show the watcher service; 1 with a reason if it cannot."""
    try:
        if action == "uninstall":
            removed = installer.uninstall(places.unit_folder, manager)
            print(f"Removed {UNIT_NAME}." if removed else f"{UNIT_NAME} is not installed.")
            return 0
        settings = find_settings(checkout, runtime, tuple(extras), places.secrets_file, which)
        unit = render_unit(settings)
        if action == "show":
            print(unit, end="")
            return 0
        if settings.op is not None and not places.secrets_file.is_file():
            print(
                f"Not installed: op fills in .env without you only with OP_SERVICE_ACCOUNT_TOKEN"
                f" in {places.secrets_file}. Add it, then install again"
                " (see docs/service.md#secrets).",
                file=sys.stderr,
            )
            return 1
        if not (settings.checkout / "config.toml").is_file():
            print(f"Warning: no config.toml in {settings.checkout}.", file=sys.stderr)
        path = installer.install(unit, places.unit_folder, manager)
    except ServiceSetupError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"Installed {path} and started it. Logs: {_LOGS}")
    if not (places.linger_folder / (user or getpass.getuser())).exists():
        print(
            "To keep it running after you log out and start it at boot: "
            "sudo loginctl enable-linger $USER"
        )
    return 0
