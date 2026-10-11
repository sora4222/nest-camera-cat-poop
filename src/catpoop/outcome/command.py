"""`catpoop train` (train extra) and `catpoop evaluate` (ONNX Runtime only)."""

import argparse
import sys
from pathlib import Path
from typing import Any

from catpoop.config import Config, ConfigError, load_config
from catpoop.outcome.evaluate import evaluate
from catpoop.outcome.examples import read_labeled_visits
from catpoop.outcome.model_files import ModelFiles, ModelInfoError

COMMANDS = ["train", "evaluate"]


def add_commands(commands: Any) -> None:
    """Add the Outcome model commands to the CLI's subparsers."""
    train = commands.add_parser(
        "train", help="train the Outcome model on the labeled dataset and export it to ONNX"
    )
    check = commands.add_parser(
        "evaluate", help="accuracy per class of the exported Outcome model on held-out Visits"
    )
    for command in (train, check):
        command.add_argument("--config", type=Path, help="config file (default: $CATPOOP_CONFIG)")


def run(args: argparse.Namespace) -> int:
    """Run `train` or `evaluate` and return the exit code."""
    try:
        config = load_config(args.config)
        if args.command == "train":
            return _train(config)
        return _evaluate(config)
    except (ConfigError, ModelInfoError, OSError) as error:
        print(error, file=sys.stderr)
        return 1


def _train(config: Config) -> int:
    try:
        from catpoop.outcome import train
    except ImportError as error:
        print(f"Training needs the train extra (`make train`): {error}", file=sys.stderr)
        return 1
    try:
        evaluation = train.train(config.paths.private_data_store, config.outcome)
    except train.TrainingError as error:
        print(error, file=sys.stderr)
        return 1
    print(evaluation.report())
    return 0


def _evaluate(config: Config) -> int:
    from catpoop.outcome.onnx_outcome import load_outcome_model

    store = config.paths.private_data_store
    settings = config.outcome
    model = load_outcome_model(ModelFiles.in_store(store, settings.models), settings.runtime)
    visits = read_labeled_visits(store / "dataset")
    evaluation = evaluate(
        model, visits, settings.validation_fraction, settings.guess_frames_per_visit
    )
    print(evaluation.report())
    return 0
