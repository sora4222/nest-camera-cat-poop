import pytest

from catpoop.domain import Outcome
from catpoop.outcome.accuracy import Accuracy

PEE, POOP, NOTHING = Outcome.PEE, Outcome.POOP, Outcome.NOTHING


def test_accuracy_per_class_and_overall():
    accuracy = Accuracy.of([(PEE, PEE), (PEE, POOP), (POOP, POOP), (NOTHING, NOTHING)])
    assert accuracy.per_class(PEE) == pytest.approx(0.5)
    assert accuracy.per_class(POOP) == 1.0
    assert accuracy.overall == pytest.approx(0.75)
    assert accuracy.total == 4


def test_a_class_with_no_examples_has_no_accuracy():
    accuracy = Accuracy.of([(PEE, PEE)])
    assert accuracy.per_class(POOP) is None
    assert Accuracy.of([]).overall is None


def test_report_lists_every_class():
    report = Accuracy.of([(PEE, PEE), (POOP, PEE)]).report("Outcome")
    assert report.splitlines() == [
        "Outcome: 50% of 2",
        "  pee: 100% of 1",
        "  poop: 0% of 1",
        "  nothing: no examples",
    ]
