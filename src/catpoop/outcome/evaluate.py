"""Measure an `OutcomeModel` on the held-out Visits of the dataset, per class.

Runs through the interface, so `make evaluate` checks the exported ONNX files exactly as
the server will use them. The Outcome Guess is only measured on frames whose time of
day is known, since a live Frame always has one.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from catpoop.domain import Frame
from catpoop.interfaces import OutcomeModel
from catpoop.outcome.accuracy import Accuracy
from catpoop.outcome.examples import LabeledVisit, split, stance_examples, surface_examples
from catpoop.outcome.features import read_picture

_NO_TIME = datetime.min.replace(tzinfo=UTC)
"""Stands in for an unknown time; the Outcome (unlike the Outcome Guess) does not use it."""


@dataclass(frozen=True)
class Evaluation:
    """Accuracy of the Outcome and of the Outcome Guess."""

    outcome: Accuracy
    guess: Accuracy

    def report(self) -> str:
        """Both accuracies, per class, for people."""
        return f"{self.outcome.report('Outcome')}\n{self.guess.report('Outcome Guess')}"


def evaluate(
    model: OutcomeModel,
    visits: Sequence[LabeledVisit],
    validation_fraction: float,
    guess_frames_per_visit: int,
) -> Evaluation:
    """How often `model` is right on the Visits held out from training."""
    _, surfaces = split(surface_examples(visits), validation_fraction)
    _, stances = split(stance_examples(visits, guess_frames_per_visit), validation_fraction)
    outcome = Accuracy.of(
        (e.outcome, model.outcome(Frame(e.taken_at or _NO_TIME, read_picture(e.picture))).best)
        for e in surfaces
    )
    guess = Accuracy.of(
        (e.outcome, model.guess(Frame(e.taken_at, read_picture(e.picture))).best)
        for e in stances
        if e.taken_at is not None
    )
    return Evaluation(outcome, guess)
