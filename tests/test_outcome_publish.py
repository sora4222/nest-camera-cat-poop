import os

import pytest

from catpoop.outcome.model_files import ModelFiles
from catpoop.outcome.publish import publish, stage


def train_into(models, text):
    staged = stage(models)
    (staged / "outcome.json").write_text(text)
    (staged / "outcome.onnx").write_text(text)
    return staged


def test_published_models_are_read_through_current(tmp_path):
    models = tmp_path / "models" / "outcome"
    publish(train_into(models, "first"), models)
    files = ModelFiles.in_store(tmp_path, models.relative_to(tmp_path))
    assert files.folder == models / "current"
    assert files.info.read_text() == "first"
    assert [p.name for p in models.iterdir() if p.name.startswith(".")] == []


def test_a_new_training_replaces_every_file_at_once(tmp_path):
    models = tmp_path / "models"
    first = publish(train_into(models, "first"), models)
    second = publish(train_into(models, "second"), models)
    files = ModelFiles(models / "current")
    assert files.info.read_text() == "second"
    assert files.outcome.read_text() == "second"
    assert first.is_dir()  # kept while a server may still be opening it
    third = publish(train_into(models, "third"), models)
    assert not first.exists()
    assert second.is_dir() and third.is_dir()


def test_unpublished_training_leaves_the_old_models(tmp_path):
    models = tmp_path / "models"
    publish(train_into(models, "old"), models)
    train_into(models, "half")  # interrupted before publish
    assert (models / "current" / "outcome.json").read_text() == "old"


def test_failed_swap_leaves_the_old_models(tmp_path, monkeypatch):
    models = tmp_path / "models"
    publish(train_into(models, "old"), models)
    staged = train_into(models, "new")

    def interrupted(source, target):
        raise OSError("power cut")

    monkeypatch.setattr(os, "replace", interrupted)
    with pytest.raises(OSError):
        publish(staged, models)
    assert (models / "current" / "outcome.json").read_text() == "old"


def test_other_folders_are_left_alone(tmp_path):
    models = tmp_path / "models"
    (models / "mine").mkdir(parents=True)
    for text in ("a", "b", "c"):
        publish(train_into(models, text), models)
    assert (models / "mine").is_dir()
