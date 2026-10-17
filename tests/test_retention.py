import json
import os
from datetime import UTC, datetime

import numpy as np

from catpoop.domain import Outcome
from catpoop.visits import retention
from catpoop.visits.retention import prune_clips, store_size
from catpoop.visits.store import Visit, VisitStore, visit_id

NOW = datetime(2026, 5, 1, tzinfo=UTC)


def add_clip(root, name, size, recorded_at):
    clips = root / "history" / "clips"
    clips.mkdir(parents=True, exist_ok=True)
    sha = name * 64
    (clips / f"{sha}.mp4").write_bytes(bytes(size))
    (clips / f"{sha}.json").write_text(json.dumps({"recorded_at": recorded_at}))
    return sha


def clips_left(root):
    return sorted(p.stem[0] for p in (root / "history" / "clips").glob("*.mp4"))


def test_store_size_counts_every_file(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x").write_bytes(bytes(10))
    (tmp_path / "y").write_bytes(bytes(5))
    assert store_size(tmp_path) == 15


def test_nothing_is_deleted_under_the_limit(tmp_path):
    add_clip(tmp_path, "a", 100, "2026-01-01T00:00:00+00:00")
    assert prune_clips(tmp_path, 10_000) == []
    assert clips_left(tmp_path) == ["a"]


def test_oldest_clips_go_first_until_under_the_limit(tmp_path):
    add_clip(tmp_path, "c", 1000, "2026-03-01T00:00:00+00:00")
    add_clip(tmp_path, "a", 1000, "2026-01-01T00:00:00+00:00")
    add_clip(tmp_path, "b", 1000, "2026-02-01T00:00:00+00:00")
    removed = prune_clips(tmp_path, 2000)
    assert [sha[0] for sha in removed] == ["a", "b"]
    assert clips_left(tmp_path) == ["c"]
    assert not (tmp_path / "history" / "clips" / f"{'a' * 64}.json").exists()


def test_clips_without_a_time_go_by_file_time(tmp_path):
    old = add_clip(tmp_path, "a", 1000, None)
    add_clip(tmp_path, "b", 1000, None)
    os.utime(tmp_path / "history" / "clips" / f"{old}.mp4", (0, 0))
    prune_clips(tmp_path, 1500)
    assert clips_left(tmp_path) == ["b"]


def test_clips_with_labeled_visits_are_kept_and_unlabeled_visits_go(tmp_path):
    labeled = add_clip(tmp_path, "a", 1000, "2026-01-01T00:00:00+00:00")
    unlabeled = add_clip(tmp_path, "b", 1000, "2026-02-01T00:00:00+00:00")
    store = VisitStore(tmp_path)
    frame = [np.zeros((4, 4, 3), np.uint8)]
    kept = store.add(Visit(visit_id(labeled, 0), labeled, 0, 2, None), frame)
    store.label(kept.id, Outcome.POOP, NOW)
    dropped = store.add(Visit(visit_id(unlabeled, 0), unlabeled, 0, 2, None), frame)
    assert prune_clips(tmp_path, 0) == [unlabeled]
    assert clips_left(tmp_path) == ["a"]
    assert store.get(dropped.id) is None
    assert store.get(kept.id) is not None


def test_a_prune_never_lists_every_visit(tmp_path, monkeypatch):
    frame = [np.zeros((4, 4, 3), np.uint8)]
    store = VisitStore(tmp_path)
    for name, month in (("a", 1), ("b", 2), ("c", 3)):
        sha = add_clip(tmp_path, name, 1000, f"2026-0{month}-01T00:00:00+00:00")
        store.add(Visit(visit_id(sha, 0), sha, 0, 2, None), frame)
    real_all = VisitStore.all

    def no_listing(self):
        raise AssertionError("listed every Visit")

    monkeypatch.setattr(VisitStore, "all", no_listing)
    assert len(prune_clips(tmp_path, 0)) == 3
    monkeypatch.setattr(VisitStore, "all", real_all)
    assert store.unlabeled() == []


def test_a_visit_labeled_after_the_clips_are_listed_keeps_its_clip(tmp_path, monkeypatch):
    sha = add_clip(tmp_path, "a", 1000, "2026-01-01T00:00:00+00:00")
    store = VisitStore(tmp_path)
    visit = store.add(Visit(visit_id(sha, 0), sha, 0, 2, None), [np.zeros((4, 4, 3), np.uint8)])
    real_age_key = retention._age_key
    labeled_once = []

    def label_after_listing(clip):
        if not labeled_once:  # `make label` runs just after the clips are listed
            labeled_once.append(store.label(visit.id, Outcome.POOP, NOW))
        return real_age_key(clip)

    monkeypatch.setattr(retention, "_age_key", label_after_listing)
    assert prune_clips(tmp_path, 0) == []
    assert clips_left(tmp_path) == ["a"]
    labeled = store.get(visit.id)
    assert labeled is not None and labeled.outcome is Outcome.POOP
    first_frame = store.frame_path(visit.id, 1)
    assert first_frame is not None and first_frame.exists()
