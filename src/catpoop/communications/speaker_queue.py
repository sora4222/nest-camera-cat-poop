"""Say texts on one Speaker from its own thread, so the watcher never waits for a speaker.

Urgent texts go ahead of any still waiting; otherwise texts are said in order. A Speaker
that fails or hangs only holds up its own queue.
"""

import itertools
import logging
import queue
import threading
from concurrent.futures import Future

from catpoop.domain import Urgency
from catpoop.interfaces import Speaker

log = logging.getLogger(__name__)


class SpeakerQueue:
    """Texts waiting for one Speaker, said by its own daemon thread."""

    def __init__(self, speaker: Speaker) -> None:
        """Say texts on `speaker`."""
        self.speaker = speaker
        self._waiting: queue.PriorityQueue[tuple[int, int, str, Future[bool]]] = (
            queue.PriorityQueue()
        )
        self._count = itertools.count()
        # Counts texts put and not yet tried, like Queue.unfinished_tasks, because
        # Queue.join() has no timeout and `wait` needs one.
        self._said = threading.Condition()
        self._unsaid = 0
        name = f"speaker {speaker.name}"
        threading.Thread(target=self._run, name=name, daemon=True).start()

    def put(self, text: str, urgency: Urgency) -> Future[bool]:
        """Say `text` soon; returns at once, with whether the Speaker said it to come."""
        future: Future[bool] = Future()
        with self._said:
            self._unsaid += 1
        self._waiting.put((urgency.say_first, next(self._count), text, future))
        return future

    def wait(self, timeout: float | None = None) -> bool:
        """Wait until every text put so far is tried; False if `timeout` seconds passed first."""
        with self._said:
            return self._said.wait_for(lambda: self._unsaid == 0, timeout)

    def _run(self) -> None:
        while True:
            _, _, text, future = self._waiting.get()
            try:
                if future.set_running_or_notify_cancel():
                    future.set_result(self._say(text))
            except Exception:
                log.exception("Speaker %s failed after saying %r", self.speaker.name, text)
            finally:
                with self._said:
                    self._unsaid -= 1
                    self._said.notify_all()

    def _say(self, text: str) -> bool:
        try:
            self.speaker.say(text)
        except Exception:
            log.exception("Speaker %s could not say %r", self.speaker.name, text)
            return False
        return True
