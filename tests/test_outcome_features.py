from datetime import UTC, datetime, timedelta, timezone

import numpy as np
import pytest

from catpoop.domain import Outcome
from catpoop.outcome.features import CLASSES, load_image, prepare_image, time_features
from catpoop.visits.video import save_jpeg

PLUS_TEN = timezone(timedelta(hours=10))


def test_classes_cover_every_outcome_once():
    assert sorted(CLASSES) == sorted(Outcome)


def test_prepare_image_resizes_to_a_square_of_floats():
    image = np.full((48, 64, 3), 200, np.uint8)
    prepared = prepare_image(image, 16)
    assert prepared.shape == (16, 16, 3)
    assert prepared.dtype == np.float32
    assert prepared == pytest.approx(np.full((16, 16, 3), 200.0))


def test_load_image_reads_a_jpeg_like_prepare_image(tmp_path):
    image = np.full((20, 30, 3), 90, np.uint8)
    save_jpeg(image, tmp_path / "frame.jpg")
    loaded = load_image(tmp_path / "frame.jpg", 8)
    assert loaded.shape == (8, 8, 3)
    assert np.abs(loaded - 90).max() < 3


def test_time_features_go_round_the_clock_in_local_time():
    midnight = time_features(datetime(2026, 1, 1, 0, 0, tzinfo=PLUS_TEN), PLUS_TEN)
    six_am = time_features(datetime(2026, 1, 1, 6, 0, tzinfo=PLUS_TEN), PLUS_TEN)
    same_six_am_in_utc = time_features(datetime(2025, 12, 31, 20, 0, tzinfo=UTC), PLUS_TEN)
    assert midnight == pytest.approx([0.0, 1.0, 1.0], abs=1e-6)
    assert six_am == pytest.approx([1.0, 0.0, 1.0], abs=1e-6)
    assert same_six_am_in_utc == pytest.approx(six_am, abs=1e-6)
    assert time_features(datetime(2026, 1, 1, 23, 59, tzinfo=PLUS_TEN), PLUS_TEN)[1] > 0.99


def test_unknown_time_is_marked():
    assert time_features(None, PLUS_TEN) == pytest.approx([0.0, 0.0, 0.0])
