import threading
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from catpoop.config import VisitSettings
from catpoop.domain import Frame
from catpoop.visits.store import VisitStore
from catpoop.watcher import recorder as recorder_module
from catpoop.watcher.recorder import LiveVisitRecorder

START = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)


def frame(seconds: float, value: int = 100) -> Frame:
    return Frame(START + timedelta(seconds=seconds), np.full((48, 64, 3), value, np.uint8))


def test_a_live_visit_is_saved_as_a_clip_waiting_for_labeling(tmp_path):
    store = tmp_path / "store"
    temp = tmp_path / "temp"
    recorder = LiveVisitRecorder(store, VisitSettings(frame_seconds=0.5), temp)
    recorder.start([frame(0), frame(0.5)])
    assert recorder.recording
    for i in range(2, 9):
        recorder.add(frame(i * 0.5))
    visit = recorder.save(START + timedelta(minutes=1))
    assert not recorder.recording
    assert (visit.source, visit.outcome, visit.frames) == ("live", None, 9)
    assert visit.end == pytest.approx(4.0, abs=0.1)
    assert visit.recorded_at == START.isoformat()
    assert [v.id for v in VisitStore(store).unlabeled()] == [visit.id]
    assert (store / "history" / "clips" / f"{visit.clip}.mp4").exists()
    assert list(temp.iterdir()) == []


def test_a_discarded_visit_leaves_nothing_behind(tmp_path):
    temp = tmp_path / "temp"
    recorder = LiveVisitRecorder(tmp_path / "store", VisitSettings(), temp)
    recorder.start([frame(0)])
    recorder.discard()
    assert not recorder.recording
    assert list(temp.iterdir()) == []
    assert not (tmp_path / "store").exists()


def test_saving_a_live_visit_keeps_the_store_under_its_size_limit(tmp_path):
    store = tmp_path / "store"
    old = store / "history" / "clips" / ("a" * 64 + ".mp4")
    old.parent.mkdir(parents=True)
    old.write_bytes(bytes(10_000))
    recorder = LiveVisitRecorder(store, VisitSettings(max_store_gb=1e-9), tmp_path / "temp")
    recorder.start([frame(0)])
    for i in range(1, 9):
        recorder.add(frame(i * 0.5))
    recorder.save(START + timedelta(minutes=1))
    assert recorder.wait_for_prune(5)
    assert not old.exists()


def test_saving_returns_without_waiting_for_the_prune(tmp_path, monkeypatch):
    release, pruned = threading.Event(), threading.Event()

    def slow_prune(store, max_bytes):
        release.wait(5)
        pruned.set()
        return []

    monkeypatch.setattr(recorder_module, "prune_clips", slow_prune)
    recorder = LiveVisitRecorder(tmp_path / "store", VisitSettings(), tmp_path / "temp")
    recorder.start([frame(0)])
    for i in range(1, 9):
        recorder.add(frame(i * 0.5))
    recorder.save(START + timedelta(minutes=1))
    assert not pruned.is_set()
    release.set()
    assert recorder.wait_for_prune(5)
    assert pruned.is_set()
