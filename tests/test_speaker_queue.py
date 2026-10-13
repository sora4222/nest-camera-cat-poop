import threading

from catpoop.communications.speaker_queue import SpeakerQueue
from catpoop.domain import Urgency


class GatedSpeaker:
    """Says nothing until `gate` is set; then remembers what it said."""

    def __init__(self, fails_on: str = "") -> None:
        self.name = "Gated"
        self.gate = threading.Event()
        self.started = threading.Event()
        self.said: list[str] = []
        self.fails_on = fails_on

    def say(self, text: str) -> None:
        self.started.set()
        self.gate.wait(5)
        if text == self.fails_on:
            raise ConnectionError("speaker unplugged")
        self.said.append(text)


def test_put_returns_before_the_speaker_has_finished():
    speaker = GatedSpeaker()
    queue = SpeakerQueue(speaker)
    queue.put("one", Urgency.NORMAL)  # would hang here if said on this thread
    assert speaker.said == []
    speaker.gate.set()
    assert queue.wait(5)
    assert speaker.said == ["one"]


def test_texts_are_said_in_order():
    speaker = GatedSpeaker()
    speaker.gate.set()
    queue = SpeakerQueue(speaker)
    for text in ("one", "two", "three"):
        queue.put(text, Urgency.NORMAL)
    assert queue.wait(5)
    assert speaker.said == ["one", "two", "three"]


def test_urgent_texts_go_ahead_of_waiting_ones():
    speaker = GatedSpeaker()
    queue = SpeakerQueue(speaker)
    queue.put("busy", Urgency.NORMAL)
    assert speaker.started.wait(5)
    queue.put("normal", Urgency.NORMAL)
    queue.put("info", Urgency.INFO)
    queue.put("urgent", Urgency.URGENT)
    speaker.gate.set()
    assert queue.wait(5)
    assert speaker.said == ["busy", "urgent", "normal", "info"]


def test_a_failure_is_logged_and_the_next_text_still_said(caplog):
    speaker = GatedSpeaker(fails_on="one")
    speaker.gate.set()
    queue = SpeakerQueue(speaker)
    queue.put("one", Urgency.NORMAL)
    queue.put("two", Urgency.NORMAL)
    assert queue.wait(5)
    assert speaker.said == ["two"]
    assert "Gated" in caplog.text and "unplugged" in caplog.text


def test_wait_gives_up_after_its_timeout():
    speaker = GatedSpeaker()
    queue = SpeakerQueue(speaker)
    queue.put("one", Urgency.NORMAL)
    assert not queue.wait(0.05)
    speaker.gate.set()
    assert queue.wait(5)
