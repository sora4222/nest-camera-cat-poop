"""Publish newly trained models all at once, so a reader sees only old or only new files.

Each training run fills a hidden folder of its own in the models folder. Publishing
renames it to a dated folder, then points the `current` symlink at it with one atomic
rename. The folder `current` pointed at before is kept, older ones are deleted.
"""

import os
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

CURRENT = "current"
"""The symlink in the models folder to the published models."""

_RUN = re.compile(r"\d{8}T\d{12}Z")


def stage(models: Path) -> Path:
    """A new empty hidden folder in `models` to write a training run into."""
    models.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(dir=models, prefix=".training-"))


def publish(staged: Path, models: Path) -> Path:
    """Make the complete training run in `staged` the current one; returns its folder."""
    name = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run = models / name
    staged.rename(run)
    current = models / CURRENT
    previous = os.readlink(current) if current.is_symlink() else None
    link = models / f".{CURRENT}-{name}"
    link.symlink_to(name, target_is_directory=True)
    try:
        os.replace(link, current)
    except OSError:
        link.unlink()
        raise
    for old in models.iterdir():
        if _RUN.fullmatch(old.name) and old.name not in (name, previous):
            shutil.rmtree(old)
    return run
