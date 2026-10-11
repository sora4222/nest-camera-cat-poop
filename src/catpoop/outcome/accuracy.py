"""Accuracy of the Outcome model, overall and per class."""

from collections.abc import Iterable
from dataclasses import dataclass

from catpoop.domain import Outcome
from catpoop.outcome.features import CLASSES


@dataclass(frozen=True)
class Accuracy:
    """How many examples of each Outcome there were and how many the model got right."""

    counts: dict[Outcome, int]
    correct: dict[Outcome, int]

    @classmethod
    def of(cls, pairs: Iterable[tuple[Outcome, Outcome]]) -> "Accuracy":
        """Count `(true, predicted)` pairs."""
        counts = dict.fromkeys(CLASSES, 0)
        correct = dict.fromkeys(CLASSES, 0)
        for true, predicted in pairs:
            counts[true] += 1
            correct[true] += true == predicted
        return cls(counts, correct)

    @property
    def total(self) -> int:
        """Number of examples."""
        return sum(self.counts.values())

    @property
    def overall(self) -> float | None:
        """Share right over all examples; None when there are none."""
        return sum(self.correct.values()) / self.total if self.total else None

    def per_class(self, outcome: Outcome) -> float | None:
        """Share of `outcome` examples that were right; None when there are none."""
        count = self.counts[outcome]
        return self.correct[outcome] / count if count else None

    def report(self, name: str) -> str:
        """A few lines for people: overall, then each class."""
        lines = [f"{name}: {_line(self.overall, self.total)}"]
        for outcome in CLASSES:
            lines.append(
                f"  {outcome.value}: {_line(self.per_class(outcome), self.counts[outcome])}"
            )
        return "\n".join(lines)


def _line(share: float | None, count: int) -> str:
    return "no examples" if share is None else f"{share:.0%} of {count}"
