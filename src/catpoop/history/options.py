"""Read history importer options from `[history.<name>]` or the command line."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from catpoop.config import ConfigError


def paths_option(name: str, options: Mapping[str, Any]) -> list[Path]:
    """The `paths` option as Paths, or `ConfigError` if there are none."""
    paths = options.get("paths") or []
    if isinstance(paths, str):
        paths = [paths]
    if not paths:
        raise ConfigError(f"history {name}: give paths on the command line or in [history.{name}]")
    return [Path(path).expanduser() for path in paths]
