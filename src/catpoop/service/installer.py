"""Put the unit file in the user's systemd folder and start it, or stop and remove it."""

import os
from pathlib import Path

from catpoop.interfaces import ServiceManager
from catpoop.service.unit_file import UNIT_NAME


def _config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def unit_folder() -> Path:
    """`$XDG_CONFIG_HOME/systemd/user`, else `~/.config/systemd/user`."""
    return _config_home() / "systemd" / "user"


def secrets_file() -> Path:
    """The service's own secrets (OP_SERVICE_ACCOUNT_TOKEN), outside any checkout."""
    return _config_home() / "catpoop" / "service.env"


def install(unit_text: str, folder: Path, manager: ServiceManager) -> Path:
    """Write the unit (replacing any old one), then start it now and with the user."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / UNIT_NAME
    path.write_text(unit_text)
    manager.reload()
    manager.enable_now(UNIT_NAME)
    return path


def uninstall(folder: Path, manager: ServiceManager) -> bool:
    """Stop and remove the unit; False if it was not installed."""
    path = folder / UNIT_NAME
    if not path.is_file():
        return False
    manager.disable_now(UNIT_NAME)
    path.unlink()
    manager.reload()
    return True
