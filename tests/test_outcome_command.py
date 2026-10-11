import sys
from datetime import UTC, datetime
from types import SimpleNamespace

import numpy as np
import pytest

from catpoop.cli import main
from catpoop.domain import Outcome
from catpoop.outcome.accuracy import Accuracy
from catpoop.outcome.evaluate import Evaluation
from catpoop.visits.store import Visit, VisitStore, visit_id


def write_config(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        f"""
[parts]
camera = "fake"
detector = "fake"
event_rules = "fake"
event_log = "memory"
presence = "off"
communications = "fake"

[paths]
private_data_store = "{tmp_path / "store"}"

[outcome]
runtime = "cpu"
validation_fraction = 0.5
"""
    )
    return path


def add_visits(store, count=12):
    visits = VisitStore(store)
    recorded_at = datetime(2026, 4, 1, 8, 0, tzinfo=UTC).isoformat()
    for i in range(count):
        clip = f"{i:02x}" * 32
        visit = Visit(visit_id(clip, 1.0), clip, 1.0, 4.0, recorded_at, outcome=Outcome.POOP)
        visits.add(visit, (np.full((8, 8, 3), (0, 9, 0), np.uint8) for _ in range(4)))


def test_evaluate_reports_accuracy_per_class_of_the_exported_models(tmp_path, capsys):
    pytest.importorskip("onnxruntime")
    from tiny_outcome_onnx import write_tiny_models

    write_tiny_models(tmp_path / "store" / "models" / "outcome")
    add_visits(tmp_path / "store")
    assert main(["evaluate", "--config", str(write_config(tmp_path))]) == 0
    out = capsys.readouterr().out
    assert "Outcome: 100% of" in out
    assert "  poop: 100% of" in out
    assert "Outcome Guess:" in out


def test_evaluate_holds_out_the_visits_the_models_were_trained_without(tmp_path, monkeypatch):
    pytest.importorskip("onnxruntime")
    from tiny_outcome_onnx import write_tiny_models

    import catpoop.outcome.command as command

    fractions = []

    def evaluate(model, visits, validation_fraction, guess_frames_per_visit):
        fractions.append(validation_fraction)
        accuracy = Accuracy.of([])
        return Evaluation(accuracy, accuracy)

    monkeypatch.setattr(command, "evaluate", evaluate)
    write_tiny_models(tmp_path / "store" / "models" / "outcome", validation_fraction=0.3)
    assert main(["evaluate", "--config", str(write_config(tmp_path))]) == 0
    assert fractions == [0.3]  # from outcome.json, not the 0.5 in config.toml


def test_evaluate_without_models_says_to_train(tmp_path, capsys):
    pytest.importorskip("onnxruntime")
    assert main(["evaluate", "--config", str(write_config(tmp_path))]) == 1
    assert "make train" in capsys.readouterr().err


def test_train_without_tensorflow_says_which_extra(tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "catpoop.outcome.train", None)
    assert main(["train", "--config", str(write_config(tmp_path))]) == 1
    assert "train extra" in capsys.readouterr().err


def test_train_prints_the_accuracy(tmp_path, monkeypatch, capsys):
    calls = []

    class TrainingError(Exception):
        pass

    def train(store, settings):
        calls.append((store, settings))
        accuracy = Accuracy.of([(Outcome.PEE, Outcome.PEE)])
        return Evaluation(accuracy, accuracy)

    fake = SimpleNamespace(train=train, TrainingError=TrainingError)
    monkeypatch.setitem(sys.modules, "catpoop.outcome.train", fake)
    assert main(["train", "--config", str(write_config(tmp_path))]) == 0
    assert calls[0][0] == tmp_path / "store"
    assert calls[0][1].runtime == "cpu"
    assert "pee: 100% of 1" in capsys.readouterr().out
