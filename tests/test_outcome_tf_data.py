from datetime import UTC, datetime

import numpy as np
import pytest

from catpoop.domain import Outcome
from catpoop.outcome.examples import Example
from catpoop.outcome.features import CLASSES
from catpoop.visits.video import save_jpeg

pytest.importorskip("tensorflow")
from catpoop.outcome.tf_data import make_dataset

AT = datetime(2026, 4, 1, 8, 0, tzinfo=UTC)


def examples(tmp_path, count=5):
    found = []
    for i in range(count):
        path = tmp_path / f"{i}.jpg"
        save_jpeg(np.full((10, 14, 3), 20 * i, np.uint8), path)
        outcome = CLASSES[i % 3]
        found.append(Example(f"v{i}", outcome, path, AT if i else None))
    return found


def test_batches_pictures_and_labels(tmp_path):
    data = make_dataset(examples(tmp_path), image_size=8, batch_size=4, with_time=False)
    inputs, labels = next(iter(data))
    assert set(inputs) == {"image"}
    assert inputs["image"].shape == (4, 8, 8, 3)
    assert labels.numpy().tolist() == [0, 1, 2, 0]
    assert float(inputs["image"][1, 0, 0, 0]) == pytest.approx(20, abs=3)
    assert CLASSES[1] == Outcome.POOP


def test_adds_the_time_of_day_for_the_guess(tmp_path):
    data = make_dataset(examples(tmp_path), image_size=8, batch_size=5, with_time=True)
    inputs, _ = next(iter(data))
    assert inputs["time"].shape == (5, 3)
    assert inputs["time"][0].numpy().tolist() == [0.0, 0.0, 0.0]
    assert inputs["time"][1, 2] == 1.0


def test_shuffled_data_keeps_every_example(tmp_path):
    data = make_dataset(examples(tmp_path), 8, 2, with_time=False, shuffle=True)
    labels = sorted(int(x) for _, batch in data for x in batch)
    assert labels == [0, 0, 1, 1, 2]
