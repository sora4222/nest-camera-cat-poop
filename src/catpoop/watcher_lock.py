"""A lock file so only one live watcher runs per user on a machine.

The OS drops the lock when the process ends, so a crash never leaves a stale lock.
The lock lives in a folder only this user can write to, and is never opened through
a symlink, so another user cannot point it at someone else's file.
"""

import errno
import fcntl
import os
import stat
import tempfile
from pathlib import Path
from types import TracebackType


class WatcherAlreadyRunning(RuntimeError):
    """Another watcher holds the lock."""


class UnsafeLockPath(RuntimeError):
    """The lock path is a symlink, or its folder is not private to this user."""


def default_lock_path() -> Path:
    """Per-user lock path shared by all worktrees: `$XDG_RUNTIME_DIR`, else a private temp dir."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir) / "catpoop-watcher.lock"
    return Path(tempfile.gettempdir()) / f"catpoop-{os.geteuid()}" / "watcher.lock"


def _check_private_folder(folder: Path) -> None:
    info = os.stat(folder, follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode):
        raise UnsafeLockPath(f"{folder} is not a real folder")
    if info.st_uid != os.geteuid():
        raise UnsafeLockPath(f"{folder} is owned by another user")
    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise UnsafeLockPath(f"{folder} can be written by other users")


class WatcherLock:
    """Hold an exclusive lock on `path` while inside the `with` block."""

    def __init__(self, path: Path) -> None:
        """Make a lock for `path`; nothing is locked until the `with` block starts."""
        self.path = path
        self._fd: int | None = None

    def __enter__(self) -> "WatcherLock":
        """Take the lock, or raise `WatcherAlreadyRunning` or `UnsafeLockPath`."""
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        _check_private_folder(self.path.parent)
        flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
        try:
            fd = os.open(self.path, flags, 0o600)
        except OSError as e:
            if e.errno == errno.ELOOP:
                raise UnsafeLockPath(f"{self.path} is a symlink") from None
            raise
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise WatcherAlreadyRunning(f"a watcher already holds {self.path}") from None
        if os.fstat(fd).st_uid == os.geteuid():
            os.ftruncate(fd, 0)
            os.write(fd, f"{os.getpid()}\n".encode())
        self._fd = fd
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Release the lock."""
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None
