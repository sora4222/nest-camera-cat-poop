"""Run a slow task (pruning the store) on its own thread, so the watcher loop never waits.

Requests made while it runs are folded into one more run after it.
"""

import logging
import threading
import time
from collections.abc import Callable

log = logging.getLogger(__name__)


class BackgroundTask:
    """Runs `task` on a daemon thread each time it is requested; one run at a time."""

    def __init__(self, task: Callable[[], None], name: str) -> None:
        """`name` says what the task does, for the thread name and the log."""
        self._task = task
        self._name = name
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._again = False

    def request(self) -> None:
        """Run the task soon; returns at once."""
        with self._lock:
            if self._thread is not None:
                self._again = True
                return
            self._thread = threading.Thread(target=self._run, name=self._name, daemon=True)
            self._thread.start()

    def wait(self, timeout: float | None = None) -> bool:
        """Wait until no run is going or due; False if `timeout` seconds passed first."""
        end = None if timeout is None else time.monotonic() + timeout
        while True:
            with self._lock:
                thread = self._thread
            if thread is None:
                return True
            left = None if end is None else max(0.0, end - time.monotonic())
            thread.join(left)
            if thread.is_alive():
                return False

    def _run(self) -> None:
        while True:
            try:
                self._task()
            except Exception:
                log.exception("%s failed", self._name)
            with self._lock:
                if not self._again:
                    self._thread = None
                    return
                self._again = False
