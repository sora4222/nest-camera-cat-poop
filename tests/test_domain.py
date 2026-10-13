import pytest

from catpoop.domain import Outcome, OutcomeScores


def test_outcome_scores_pick_the_most_likely_outcome():
    scores = OutcomeScores({Outcome.PEE: 0.2, Outcome.POOP: 0.7, Outcome.NOTHING: 0.1})
    assert scores.best == Outcome.POOP
    assert scores[Outcome.PEE] == pytest.approx(0.2)
