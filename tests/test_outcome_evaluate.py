from datetime import UTC, datetime

import numpy as np

from catpoop.domain import Frame, Outcome, OutcomeScores
from catpoop.outcome.evaluate import evaluate
from catpoop.outcome.examples import is_validation, read_labeled_visits
from catpoop.visits.store import Visit, VisitStore, visit_id

RECORDED = datetime(2026, 4, 1, 8, 0, tzinfo=UTC).isoformat()


class AlwaysPoop:
    """A fake OutcomeModel that says Poop and remembers what it was shown."""

    def __init__(self):
        self.surfaces: list[Frame] = []
        self.stances: list[Frame] = []

    def _poop(self):
        return OutcomeScores({Outcome.PEE: 0.1, Outcome.POOP: 0.8, Outcome.NOTHING: 0.1})

    def outcome(self, surface):
        self.surfaces.append(surface)
        return self._poop()

    def guess(self, stance):
        self.stances.append(stance)
        return self._poop()


def make_dataset(tmp_path, count=30):
    store = VisitStore(tmp_path)
    for i in range(count):
        clip = f"{i:02x}" * 32
        outcome = Outcome.POOP if i % 2 else Outcome.PEE
        recorded_at = None if i % 3 == 0 else RECORDED
        visit = Visit(visit_id(clip, 1.0), clip, 1.0, 5.0, recorded_at, outcome=outcome)
        store.add(visit, (np.full((6, 6, 3), 50, np.uint8) for _ in range(4)))
    return read_labeled_visits(tmp_path / "dataset")


def test_evaluates_only_held_out_visits(tmp_path):
    visits = make_dataset(tmp_path)
    held_out = [v for v in visits if is_validation(v.id, 0.5)]
    model = AlwaysPoop()
    result = evaluate(model, visits, validation_fraction=0.5, guess_frames_per_visit=2)
    assert result.outcome.total == len(held_out) > 0
    poops = sum(v.outcome == Outcome.POOP for v in held_out)
    assert result.outcome.per_class(Outcome.POOP) == 1.0
    assert result.outcome.correct[Outcome.POOP] == poops
    assert result.outcome.per_class(Outcome.PEE) in (0.0, None)
    assert model.surfaces[0].image.shape == (6, 6, 3)
    assert model.surfaces[0].image.dtype == np.uint8


def test_the_guess_is_measured_on_visits_with_a_known_time(tmp_path):
    visits = make_dataset(tmp_path)
    model = AlwaysPoop()
    result = evaluate(model, visits, validation_fraction=0.5, guess_frames_per_visit=2)
    timed = [v for v in visits if is_validation(v.id, 0.5) and v.recorded_at is not None]
    assert result.guess.total == 2 * len(timed)
    assert all(frame.taken_at is not None for frame in model.stances)
    assert "Outcome Guess" in result.report()
    assert "Outcome:" in result.report()
