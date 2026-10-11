import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from catpoop.domain import Frame, Outcome
from catpoop.outcome.model_files import ModelFiles, ModelInfoError, load_model_info
from catpoop.outcome.onnx_outcome import load_outcome_model

ort = pytest.importorskip("onnxruntime")
from tiny_outcome_onnx import SIZE, ZONE, write_tiny_models  # noqa: E402

# Midnight and 6am in ZONE (UTC+10), given in UTC so the zone in outcome.json matters.
MIDNIGHT = datetime(2025, 12, 31, 14, 0, tzinfo=UTC)
SIX_AM = datetime(2025, 12, 31, 20, 0, tzinfo=UTC)


def picture(red=0, green=0, blue=0, height=9, width=12):
    return np.full((height, width, 3), (red, green, blue), np.uint8)


def test_model_info_is_saved_next_to_the_models(tmp_path):
    files = write_tiny_models(tmp_path / "models", validation_fraction=0.3)
    info = load_model_info(files)
    assert info.validation_fraction == 0.3
    assert info.image_size == SIZE
    assert list(info.classes) == [Outcome.PEE, Outcome.POOP, Outcome.NOTHING]
    assert str(info.zone) == ZONE


def test_missing_or_wrong_model_info_is_an_error(tmp_path):
    with pytest.raises(ModelInfoError, match=r"make train"):
        load_model_info(ModelFiles(tmp_path))
    (tmp_path / "outcome.json").write_text(json.dumps({"classes": ["pee", "cake"]}))
    with pytest.raises(ModelInfoError, match=r"outcome\.json"):
        load_model_info(ModelFiles(tmp_path))


def test_unknown_time_zone_in_model_info_is_an_error(tmp_path):
    files = write_tiny_models(tmp_path)
    info = json.loads(files.info.read_text())
    files.info.write_text(json.dumps({**info, "timezone": "Mars/Olympus"}))
    with pytest.raises(ModelInfoError, match=r"Mars/Olympus"):
        load_model_info(files)
    del info["timezone"]
    files.info.write_text(json.dumps(info))
    with pytest.raises(ModelInfoError, match=r"timezone"):
        load_model_info(files)


def test_outcome_comes_from_the_litter_surface(tmp_path):
    model = load_outcome_model(write_tiny_models(tmp_path), "cpu")
    assert model.outcome(Frame(MIDNIGHT, picture(green=9))).best == Outcome.POOP
    scores = model.outcome(Frame(MIDNIGHT, picture(blue=9)))
    assert scores.best == Outcome.NOTHING
    assert sum(scores.scores.values()) == pytest.approx(1.0)


def test_outcome_guess_uses_the_time_of_day_in_the_trained_zone(tmp_path):
    model = load_outcome_model(write_tiny_models(tmp_path), "cpu")
    assert model.guess(Frame(MIDNIGHT, picture(red=9))).best == Outcome.PEE
    assert model.guess(Frame(SIX_AM, picture(red=9))).best == Outcome.POOP


def test_missing_model_file_is_an_error(tmp_path):
    files = write_tiny_models(tmp_path)
    files.guess.unlink()
    with pytest.raises(ModelInfoError, match=r"outcome_guess\.onnx"):
        load_outcome_model(files, "cpu")


def test_models_folder_is_inside_the_store_unless_absolute(tmp_path):
    assert (
        ModelFiles.in_store(tmp_path, Path("models/outcome")).folder == tmp_path / "models/outcome"
    )
    assert ModelFiles.in_store(tmp_path, Path("/elsewhere")).folder == Path("/elsewhere")
