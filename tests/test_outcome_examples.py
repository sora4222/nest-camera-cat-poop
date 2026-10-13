from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from catpoop.domain import Outcome
from catpoop.outcome.examples import (
    is_validation,
    read_labeled_visits,
    split,
    stance_examples,
    surface_examples,
)
from catpoop.visits.store import Visit, VisitStore, visit_id

RECORDED = datetime(2026, 4, 1, 8, 0, tzinfo=UTC)
RECORDED_AT = RECORDED.isoformat()


def add(store, clip, outcome, frames=8, start=10.0, recorded_at=RECORDED_AT):
    visit = Visit(visit_id(clip, start), clip, start, start + 7, recorded_at, outcome=outcome)
    pictures = (np.full((8, 8, 3), i, np.uint8) for i in range(frames))
    return store.add(visit, pictures)


def test_reads_labeled_visits_from_the_manifest(tmp_path):
    store = VisitStore(tmp_path)
    poop = add(store, "aa" * 32, Outcome.POOP)
    add(store, "bb" * 32, None)
    [visit] = read_labeled_visits(tmp_path / "dataset")
    assert visit.id == poop.id
    assert visit.outcome == Outcome.POOP
    assert visit.frames_dir == tmp_path / "dataset" / "poop" / poop.id
    assert visit.frame_count == 8
    assert visit.recorded_at == RECORDED
    assert visit.start == 10.0
    assert visit.end == 17.0


def test_no_manifest_means_no_visits(tmp_path):
    assert read_labeled_visits(tmp_path / "dataset") == []


def test_the_litter_surface_is_the_last_frame(tmp_path):
    store = VisitStore(tmp_path)
    visit = add(store, "aa" * 32, Outcome.PEE)
    [example] = surface_examples(read_labeled_visits(tmp_path / "dataset"))
    assert example.visit_id == visit.id
    assert example.outcome == Outcome.PEE
    assert example.picture.name == "frame_0008.jpg"
    assert example.picture.exists()
    assert example.taken_at == RECORDED + timedelta(seconds=17)


def test_the_stance_comes_from_frames_in_the_middle_of_the_visit(tmp_path):
    store = VisitStore(tmp_path)
    add(store, "aa" * 32, Outcome.POOP, frames=9)
    examples = stance_examples(read_labeled_visits(tmp_path / "dataset"), per_visit=3)
    assert [e.picture.name for e in examples] == [
        "frame_0003.jpg",
        "frame_0005.jpg",
        "frame_0007.jpg",
    ]
    assert examples[1].taken_at == RECORDED + timedelta(seconds=13.5)
    assert {e.outcome for e in examples} == {Outcome.POOP}


def test_short_visits_give_every_frame_they_have(tmp_path):
    store = VisitStore(tmp_path)
    add(store, "aa" * 32, Outcome.NOTHING, frames=1, recorded_at=None)
    [example] = stance_examples(read_labeled_visits(tmp_path / "dataset"), per_visit=5)
    assert example.picture.name == "frame_0001.jpg"
    assert example.taken_at is None


def test_the_split_keeps_each_visit_on_one_side_and_never_changes():
    ids = [visit_id(f"{i:02x}" * 32, 1.0) for i in range(200)]
    held_out = [i for i in ids if is_validation(i, 0.2)]
    assert held_out == [i for i in ids if is_validation(i, 0.2)]
    assert len(held_out) == pytest.approx(40, abs=15)
    assert not any(is_validation(i, 0.0) for i in ids)


def test_split_sorts_examples_into_training_and_validation(tmp_path):
    store = VisitStore(tmp_path)
    for i in range(20):
        add(store, f"{i:02x}" * 32, Outcome.PEE, frames=3)
    examples = stance_examples(read_labeled_visits(tmp_path / "dataset"), per_visit=2)
    training, validation = split(examples, 0.3)
    assert len(training) + len(validation) == 40
    assert {e.visit_id for e in training}.isdisjoint({e.visit_id for e in validation})
    assert all(is_validation(e.visit_id, 0.3) for e in validation)
