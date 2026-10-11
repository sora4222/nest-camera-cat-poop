"""Say texts on one Speaker from its own thread, so the watcher never waits for a speaker.

Urgent texts go ahead of any still waiting; otherwise texts are said in order. A Speaker
that fails or hangs only holds up its own queue.
"""

import itertools
import logging
import queue
import threading

from catpoop.domain import Urgency
from catpoop.interfaces import Speaker

log = logging.getLogger(__name__)

_ORDER = {Urgency.URGENT: 0, Urgency.NORMAL: 1, Urgency.INFO: 1}


class SpeakerQueue:
    """Texts waiting for one Speaker, said by a daemon thread started on the first `put`."""

    def __init__(self, speaker: Speaker) -> None:
        """Say texts on `speaker`."""
        self.speaker = speaker
        self._waiting: queue.PriorityQueue[tuple[int, int, str]] = queue.PriorityQueue()
        self._count = itertools.count()
        self._said = threading.Condition()
        self._unsaid = 0
        self._thread: threading.Thread | None = None

    def put(self, text: str, urgency: Urgency) -> None:
        """Say `text` soon; returns at once."""
        with self._said:
            self._unsaid += 1
            self._waiting.put((_ORDER[urgency], next(self._count), text))
            if self._thread is None:
                name = f"speaker {self.speaker.name}"
                self._thread = threading.Thread(target=self._run, name=name, daemon=True)
                self._thread.start()

    def wait(self, timeout: float | None = None) -> bool:
        """Wait until every text put so far is said; False if `timeout` seconds passed first."""
        with self._said:
            return self._said.wait_for(lambda: self._unsaid == 0, timeout)

    def _run(self) -> None:
        while True:
            _, _, text = self._waiting.get()
            try:
                self.speaker.say(text)
            except Exception:
                log.exception("Speaker %s could not say %r", self.speaker.name, text)
            finally:
                with self._said:
                    self._unsaid -= 1
                    self._said.notify_all()
