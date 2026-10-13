import json
from datetime import UTC, datetime

import numpy as np
from fake_video import write_clip

from catpoop.config import VisitSettings
from catpoop.domain import Detection, Frame, Outcome
from catpoop.visits.cut import cut_clips
from catpoop.visits.store import VisitStore

SETTINGS = VisitSettings(frame_seconds=0.5, end_gap_seconds=1, min_seconds=1, padding_seconds=0.5)
DARK, BRIGHT = 20, 230


class BrightIsCat:
    """Sees the Cat in bright frames."""

    def __init__(self):
        self.frames: list[Frame] = []

    def detect(self, frame: Frame) -> list[Detection]:
        self.frames.append(frame)
        if np.asarray(frame.image).mean() > 128:
            return [Detection("cat", 0.9, (0.4, 0.4, 0.6, 0.6))]
        return []


def add_clip(store_path, name, brightness, recorded_at="2026-04-01T08:00:00+00:00"):
    clips = store_path / "history" / "clips"
    clips.mkdir(parents=True, exist_ok=True)
    sha = name * 64
    write_clip(clips / f"{sha}.mp4", brightness)
    (clips / f"{sha}.json").write_text(json.dumps({"recorded_at": recorded_at, "sources": []}))
    return sha


def test_cuts_each_visit_out_of_a_clip(tmp_path):
    # 4 frames a second: dark 2s, bright 2s, dark 2s.
    sha = add_clip(tmp_path, "a", [DARK] * 8 + [BRIGHT] * 8 + [DARK] * 8)
    detector = BrightIsCat()
    counts = cut_clips(tmp_path, detector, SETTINGS)
    assert (counts.clips, counts.visits) == (1, 1)
    (visit,) = VisitStore(tmp_path).unlabeled()
    assert visit.clip == sha
    assert (visit.start, visit.end) == (1.5, 4.0)
    assert visit.recorded_at == "2026-04-01T08:00:00+00:00"
    assert visit.frames == 6  # 1.5, 2.0, ... 4.0
    assert detector.frames[1].taken_at.isoformat() == "2026-04-01T08:00:00.500000+00:00"


def test_clips_are_cut_once(tmp_path):
    add_clip(tmp_path, "a", [BRIGHT] * 8)
    cut_clips(tmp_path, BrightIsCat(), SETTINGS)
    detector = BrightIsCat()
    counts = cut_clips(tmp_path, detector, SETTINGS)
    assert (counts.clips, counts.visits) == (0, 0)
    assert detector.frames == []


def test_clip_with_no_visit_is_still_marked_cut(tmp_path):
    sha = add_clip(tmp_path, "b", [DARK] * 8, recorded_at=None)
    assert cut_clips(tmp_path, BrightIsCat(), SETTINGS).visits == 0
    assert VisitStore(tmp_path).is_scanned(sha)


def test_broken_clip_is_skipped(tmp_path):
    clips = tmp_path / "history" / "clips"
    clips.mkdir(parents=True)
    (clips / f"{'c' * 64}.mp4").write_bytes(b"broken")
    counts = cut_clips(tmp_path, BrightIsCat(), SETTINGS)
    assert (counts.clips, counts.failed) == (0, 1)


def test_labeled_visits_are_not_cut_again(tmp_path):
    sha = add_clip(tmp_path, "a", [BRIGHT] * 8)
    cut_clips(tmp_path, BrightIsCat(), SETTINGS)
    store = VisitStore(tmp_path)
    (visit,) = store.unlabeled()
    store.label(visit.id, Outcome.POOP, datetime(2026, 5, 1, tzinfo=UTC))
    store.remove_unlabeled(sha)
    assert cut_clips(tmp_path, BrightIsCat(), SETTINGS).visits == 0
    kept = store.get(visit.id)
    assert kept is not None
    assert kept.outcome is Outcome.POOP


def test_visit_at_the_end_of_a_clip_runs_to_its_end(tmp_path):
    add_clip(tmp_path, "a", [DARK] * 8 + [BRIGHT] * 8)
    cut_clips(tmp_path, BrightIsCat(), SETTINGS)
    (visit,) = VisitStore(tmp_path).unlabeled()
    assert (visit.start, visit.end) == (1.5, 4.0)
