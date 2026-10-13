"""What the watcher service runs: the checkout, the tools and where secrets come from."""

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


class ServiceSetupError(Exception):
    """The service cannot be set up on this machine, with a readable reason."""


@dataclass(frozen=True)
class ServiceSettings:
    """Everything the unit file is made from. Paths are absolute."""

    checkout: Path
    uv: Path
    runtime: str = "cpu"
    extras: tuple[str, ...] = ()
    env_file: Path | None = None
    """The checkout's `.env`, if there is one."""
    op: Path | None = None
    """The 1Password CLI; when set, `op://` references in `env_file` are filled in."""
    secrets_file: Path | None = None
    """An optional file of variables for the service itself (OP_SERVICE_ACCOUNT_TOKEN)."""


def find_settings(
    checkout: Path,
    runtime: str,
    extras: tuple[str, ...],
    secrets_file: Path,
    which: Callable[[str], str | None] = shutil.which,
) -> ServiceSettings:
    """Settings for `checkout`, finding `uv` and `op` the way the Makefile does."""
    uv = which("uv")
    if uv is None:
        raise ServiceSetupError("uv is not on PATH; install it first (see docs/setup.md)")
    checkout = checkout.resolve()
    env_file = checkout / ".env"
    op = which("op")
    return ServiceSettings(
        checkout=checkout,
        uv=Path(uv).resolve(),
        runtime=runtime,
        extras=extras,
        env_file=env_file if env_file.is_file() else None,
        op=Path(op).resolve() if op else None,
        secrets_file=secrets_file,
    )
