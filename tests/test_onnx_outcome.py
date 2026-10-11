import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from catpoop.domain import Frame, Outcome
from catpoop.outcome.model_files import ModelFiles, ModelInfoError, load_model_info
from catpoop.outcome.onnx_outcome import load_outcome_model

ort = pytest.importorskip("onnxruntime")
from tiny_outcome_onnx import SIZE, write_tiny_models  # noqa: E402

ZONE = timezone(timedelta(hours=10))
MIDNIGHT = datetime(2026, 1, 1, 0, 0, tzinfo=ZONE)
SIX_AM = datetime(2026, 1, 1, 6, 0, tzinfo=ZONE)


def picture(red=0, green=0, blue=0, height=9, width=12):
    return np.full((height, width, 3), (red, green, blue), np.uint8)


def test_model_info_is_saved_next_to_the_models(tmp_path):
    files = write_tiny_models(tmp_path / "models")
    info = load_model_info(files)
    assert info.image_size == SIZE
    assert list(info.classes) == [Outcome.PEE, Outcome.POOP, Outcome.NOTHING]


def test_missing_or_wrong_model_info_is_an_error(tmp_path):
    with pytest.raises(ModelInfoError, match=r"make train"):
        load_model_info(ModelFiles(tmp_path))
    (tmp_path / "outcome.json").write_text(json.dumps({"classes": ["pee", "cake"]}))
    with pytest.raises(ModelInfoError, match=r"outcome\.json"):
        load_model_info(ModelFiles(tmp_path))


def test_outcome_comes_from_the_litter_surface(tmp_path):
    model = load_outcome_model(write_tiny_models(tmp_path), "cpu")
    assert model.outcome(Frame(MIDNIGHT, picture(green=9))).best == Outcome.POOP
    scores = model.outcome(Frame(MIDNIGHT, picture(blue=9)))
    assert scores.best == Outcome.NOTHING
    assert sum(scores.scores.values()) == pytest.approx(1.0)


def test_outcome_guess_uses_the_time_of_day(tmp_path):
    model = load_outcome_model(write_tiny_models(tmp_path), "cpu", zone=ZONE)
    assert model.guess(Frame(MIDNIGHT, picture(red=9))).best == Outcome.PEE
    assert model.guess(Frame(SIX_AM, picture(red=9))).best == Outcome.POOP


def test_missing_model_file_is_an_error(tmp_path):
    files = write_tiny_models(tmp_path)
    files.guess.unlink()
    with pytest.raises(ModelInfoError, match=r"outcome_guess\.onnx"):
        load_outcome_model(files, "cpu")
