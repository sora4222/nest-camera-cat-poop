"""Train the Outcome and Outcome Guess models, export them to ONNX and measure them (train extra).

Accuracy is measured with the exported ONNX files, as the server will run them. Only when
that works are the new files published, all at once.
"""

import shutil
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from zoneinfo import ZoneInfo

import keras

from catpoop.config import OutcomeSettings
from catpoop.outcome.evaluate import Evaluation, evaluate
from catpoop.outcome.examples import (
    Example,
    read_labeled_visits,
    split,
    stance_examples,
    surface_examples,
)
from catpoop.outcome.features import CLASSES
from catpoop.outcome.model_files import ModelFiles, save_model_info
from catpoop.outcome.network import build_model
from catpoop.outcome.onnx_export import export_onnx
from catpoop.outcome.onnx_outcome import load_outcome_model
from catpoop.outcome.publish import publish, stage
from catpoop.outcome.tf_data import make_dataset


class TrainingError(Exception):
    """There is nothing to train on."""


def class_weights(examples: Sequence[Example]) -> dict[int, float]:
    """A weight per class index present, so rare Outcomes count as much as common ones."""
    counts = Counter(CLASSES.index(e.outcome) for e in examples)
    return {index: len(examples) / (len(counts) * count) for index, count in counts.items()}


def train(
    private_data_store: Path, settings: OutcomeSettings, log: Callable[[str], None] = print
) -> Evaluation:
    """Train both models on the dataset in `private_data_store` and save them in its models."""
    dataset = private_data_store / "dataset"
    visits = read_labeled_visits(dataset)
    if not visits:
        raise TrainingError(f"no labeled Visits in {dataset}; label some with `make label`")
    log(f"Training on {len(visits)} labeled Visits")
    models = private_data_store / settings.models
    staged = ModelFiles(stage(models))
    try:
        log("Outcome (litter surface after the Visit)")
        _fit(surface_examples(visits), staged.outcome, settings, with_time=False)
        log("Outcome Guess (the Cat's stance and the time of day)")
        stances = stance_examples(visits, settings.guess_frames_per_visit)
        _fit(stances, staged.guess, settings, with_time=True)
        save_model_info(
            staged, settings.image_size, settings.timezone, settings.validation_fraction
        )
        model = load_outcome_model(staged, "cpu")
        evaluation = evaluate(
            model, visits, settings.validation_fraction, settings.guess_frames_per_visit
        )
        files = ModelFiles(publish(staged.folder, models))
    except BaseException:
        shutil.rmtree(staged.folder, ignore_errors=True)
        raise
    log(f"Published {files.folder}")
    return evaluation


def _fit(
    examples: Sequence[Example], output: Path, settings: OutcomeSettings, with_time: bool
) -> None:
    """Train one model on `examples` and export it to `output`."""
    training, validation = split(examples, settings.validation_fraction)
    if not training:
        raise TrainingError("every Visit is held out for validation; lower validation_fraction")

    zone = ZoneInfo(settings.timezone)

    def data(part: Sequence[Example], shuffle: bool):
        return make_dataset(
            part, settings.image_size, settings.batch_size, with_time, zone, shuffle
        )

    model = build_model(settings.image_size, settings.backbone, with_time)
    callbacks = []
    if validation:
        callbacks.append(
            keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True, verbose=1)
        )
    model.fit(
        data(training, shuffle=True),
        validation_data=data(validation, shuffle=False) if validation else None,
        epochs=settings.epochs,
        class_weight=class_weights(training),
        callbacks=callbacks,
        shuffle=False,  # the tf.data pipeline shuffles
        verbose=2,
    )
    export_onnx(model, output, settings.image_size, with_time)
