"""Run a slow task (pruning the store) on its own thread, apart from the watcher loop.

Requests made while it runs are folded into one more run after it.
"""

import logging
import threading
from collections.abc import Callable

log = logging.getLogger(__name__)


class BackgroundTask:
    """Runs `task` on a daemon thread each time it is requested; one run at a time."""

    def __init__(self, task: Callable[[], None], name: str) -> None:
        """`name` says what the task does, for the thread name and the log."""
        self._task = task
        self._name = name
        self._done = threading.Condition()
        self._thread: threading.Thread | None = None
        self._again = False

    def request(self) -> None:
        """Run the task soon; returns at once."""
        with self._done:
            if self._thread is not None:
                self._again = True
                return
            self._thread = threading.Thread(target=self._run, name=self._name, daemon=True)
            self._thread.start()

    def wait(self, timeout: float | None = None) -> bool:
        """Wait until no run is going or due; False if `timeout` seconds passed first."""
        with self._done:
            return self._done.wait_for(lambda: self._thread is None, timeout)

    def _run(self) -> None:
        while True:
            try:
                self._task()
            except Exception:
                log.exception("%s failed", self._name)
            with self._done:
                if not self._again:
                    self._thread = None
                    self._done.notify_all()
                    return
                self._again = False
