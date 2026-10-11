import csv
from datetime import UTC, datetime

import numpy as np
import pytest

from catpoop.domain import Outcome
from catpoop.visits.store import Visit, VisitStore, visit_id

SHA = "ab" * 32
NOW = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)


def images(count):
    return (np.full((8, 8, 3), 10 * i, np.uint8) for i in range(count))


def visit(start=1.5, clip=SHA, recorded_at="2026-04-01T08:00:00+00:00", **kwargs):
    return Visit(visit_id(clip, start), clip, start, start + 4, recorded_at, **kwargs)


def test_visit_id_comes_from_clip_and_start():
    assert visit_id(SHA, 1.5) == "abababababababab-0001500"


def test_new_visit_is_unlabeled_with_its_frames(tmp_path):
    store = VisitStore(tmp_path)
    saved = store.add(visit(), images(3))
    assert saved.frames == 3
    assert store.unlabeled() == [saved]
    assert store.get(saved.id) == saved
    assert store.frame_path(saved.id, 1) == (
        tmp_path / "visits" / "frames" / saved.id / "frame_0001.jpg"
    )
    assert store.frame_path(saved.id, 4) is None


def test_unlabeled_visits_come_oldest_first(tmp_path):
    store = VisitStore(tmp_path)
    late = store.add(visit(clip="cd" * 32, recorded_at="2026-04-02T00:00:00+00:00"), images(1))
    early_second = store.add(visit(start=30), images(1))
    early_first = store.add(visit(start=2), images(1))
    assert [v.id for v in store.unlabeled()] == [early_first.id, early_second.id, late.id]


def test_labeling_moves_frames_into_the_dataset_and_writes_the_manifest(tmp_path):
    store = VisitStore(tmp_path)
    saved = store.add(visit(), images(2))
    labeled = store.label(saved.id, Outcome.POOP, NOW)
    assert labeled.outcome is Outcome.POOP
    assert store.unlabeled() == []
    folder = tmp_path / "dataset" / "poop" / saved.id
    assert sorted(p.name for p in folder.iterdir()) == ["frame_0001.jpg", "frame_0002.jpg"]
    assert store.frame_path(saved.id, 2) == folder / "frame_0002.jpg"
    with (tmp_path / "dataset" / "manifest.csv").open() as manifest:
        (row,) = list(csv.DictReader(manifest))
    assert row["visit_id"] == saved.id
    assert row["outcome"] == "poop"
    assert row["frames_dir"] == f"poop/{saved.id}"
    assert row["frame_count"] == "2"
    assert row["clip"] == f"history/clips/{SHA}.mp4"
    assert row["start_seconds"] == "1.5"
    assert row["labeled_at"] == NOW.isoformat()


def test_labeling_again_moves_the_visit(tmp_path):
    store = VisitStore(tmp_path)
    saved = store.add(visit(), images(1))
    store.label(saved.id, Outcome.POOP, NOW)
    store.label(saved.id, Outcome.PEE, NOW)
    assert not (tmp_path / "dataset" / "poop" / saved.id).exists()
    assert (tmp_path / "dataset" / "pee" / saved.id / "frame_0001.jpg").exists()
    manifest = (tmp_path / "dataset" / "manifest.csv").read_text()
    assert manifest.count(saved.id) == 2  # visit_id and frames_dir of one row


def test_visit_added_with_an_outcome_goes_straight_to_the_dataset(tmp_path):
    store = VisitStore(tmp_path)
    saved = store.add(
        visit(source="manual", outcome=Outcome.PEE, labeled_at=NOW.isoformat()), images(2)
    )
    assert (tmp_path / "dataset" / "pee" / saved.id / "frame_0002.jpg").exists()
    assert "manual" in (tmp_path / "dataset" / "manifest.csv").read_text()


def test_unknown_or_odd_ids_are_refused(tmp_path):
    store = VisitStore(tmp_path)
    assert store.get("../../etc") is None
    assert store.frame_path("../x", 1) is None
    with pytest.raises(KeyError):
        store.label("abababababababab-0000000", Outcome.POOP, NOW)


def test_removing_a_clip_keeps_its_labeled_visits(tmp_path):
    store = VisitStore(tmp_path)
    kept = store.add(visit(start=1), images(1))
    store.label(kept.id, Outcome.NOTHING, NOW)
    gone = store.add(visit(start=20), images(1))
    store.mark_scanned(SHA)
    store.remove_unlabeled(SHA)
    assert store.get(gone.id) is None
    assert not (tmp_path / "visits" / "frames" / gone.id).exists()
    assert store.get(kept.id) is not None
    assert not store.is_scanned(SHA)
    assert store.labeled_clips() == {SHA}


def test_scanned_clips_are_remembered(tmp_path):
    store = VisitStore(tmp_path)
    assert not store.is_scanned(SHA)
    store.mark_scanned(SHA)
    assert VisitStore(tmp_path).is_scanned(SHA)
