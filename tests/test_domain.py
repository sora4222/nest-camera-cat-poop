from datetime import UTC, datetime

import pytest

from catpoop.domain import Event, Outcome, OutcomeScores, Urgency


def test_outcome_scores_pick_the_most_likely_outcome():
    scores = OutcomeScores({Outcome.PEE: 0.2, Outcome.POOP: 0.7, Outcome.NOTHING: 0.1})
    assert scores.best == Outcome.POOP
    assert scores[Outcome.PEE] == pytest.approx(0.2)


def test_events_are_announced_unless_they_are_only_for_the_log():
    at = datetime(2026, 1, 1, tzinfo=UTC)
    assert Event("poop", Urgency.NORMAL, at).announce
    assert not Event("visit_ended", Urgency.INFO, at, announce=False).announce
