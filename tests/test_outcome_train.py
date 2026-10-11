from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from catpoop.config import OutcomeSettings
from catpoop.domain import Frame, Outcome
from catpoop.outcome.features import CLASSES
from catpoop.outcome.model_files import ModelFiles, load_model_info
from catpoop.visits.store import Visit, VisitStore, visit_id

pytest.importorskip("tensorflow")
pytest.importorskip("tf2onnx")
pytest.importorskip("onnxruntime")
from catpoop.outcome.examples import Example
from catpoop.outcome.onnx_outcome import load_outcome_model
from catpoop.outcome.train import TrainingError, class_weights, train

COLOURS = {Outcome.PEE: (200, 0, 0), Outcome.POOP: (0, 200, 0), Outcome.NOTHING: (0, 0, 200)}
SETTINGS = OutcomeSettings(
    backbone="small", image_size=32, epochs=2, batch_size=4, validation_fraction=0.4
)


def make_dataset(store: Path, per_class: int = 4) -> None:
    visits = VisitStore(store)
    recorded_at = datetime(2026, 4, 1, 8, 0, tzinfo=UTC).isoformat()
    for n, outcome in enumerate(CLASSES * per_class):
        clip = f"{n:02x}" * 32
        visit = Visit(visit_id(clip, 1.0), clip, 1.0, 4.0, recorded_at, outcome=outcome)
        visits.add(visit, (np.full((24, 32, 3), COLOURS[outcome], np.uint8) for _ in range(4)))


def test_trains_exports_and_reports_both_models(tmp_path):
    make_dataset(tmp_path)
    evaluation = train(tmp_path, SETTINGS)
    files = ModelFiles.in_store(tmp_path, SETTINGS.models)
    assert files.outcome.is_file()
    assert files.guess.is_file()
    assert load_model_info(files).image_size == 32
    assert evaluation.outcome.total > 0
    assert evaluation.guess.total > 0
    model = load_outcome_model(files, "cpu")
    picture = np.full((24, 32, 3), COLOURS[Outcome.POOP], np.uint8)
    scores = model.guess(Frame(datetime(2026, 4, 2, 8, 0, tzinfo=UTC), picture))
    assert sum(scores.scores.values()) == pytest.approx(1.0, abs=1e-4)


def test_no_labeled_visits_is_an_error(tmp_path):
    with pytest.raises(TrainingError, match="make label"):
        train(tmp_path, SETTINGS)


def test_rare_outcomes_weigh_more():
    examples = [
        Example("v", o, Path("x.jpg"), None) for o in [*[Outcome.NOTHING] * 3, Outcome.POOP]
    ]
    weights = class_weights(examples)
    assert weights[CLASSES.index(Outcome.POOP)] == pytest.approx(3 * weights[2])
    assert CLASSES.index(Outcome.PEE) not in weights
