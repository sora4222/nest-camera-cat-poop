"""A lock file so only one live watcher runs on a machine.

The OS drops the lock when the process ends, so a crash never leaves a stale lock.
"""

import fcntl
import os
from pathlib import Path
from types import TracebackType


class WatcherAlreadyRunning(RuntimeError):
    """Another watcher holds the lock."""


class WatcherLock:
    """Hold an exclusive lock on `path` while inside the `with` block."""

    def __init__(self, path: Path) -> None:
        """Make a lock for `path`; nothing is locked until the `with` block starts."""
        self.path = path
        self._fd: int | None = None

    def __enter__(self) -> "WatcherLock":
        """Take the lock, or raise `WatcherAlreadyRunning`."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise WatcherAlreadyRunning(f"a watcher already holds {self.path}") from None
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
