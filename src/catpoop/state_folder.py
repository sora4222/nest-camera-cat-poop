"""The user's state folder for the server's small files, outside any worktree."""

import os
from pathlib import Path


def state_folder() -> Path:
    """`$XDG_STATE_HOME/catpoop`, else `~/.local/state/catpoop`."""
    base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / "catpoop"
