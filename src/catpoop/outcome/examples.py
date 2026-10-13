"""Training examples from the labeled dataset (`dataset/manifest.csv`, see docs/visits.md).

The Outcome is learned from the last frame of a Visit, when the Cat has left the litter
surface. The Outcome Guess is learned from frames in the middle of the Visit, when the
Cat is in its stance. Visits are split into training and validation by their id, so a
Visit is always on the same side.
"""

import csv
import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from catpoop.domain import Outcome
from catpoop.visits.store import frame_name


@dataclass(frozen=True)
class LabeledVisit:
    """One row of the dataset manifest."""

    id: str
    outcome: Outcome
    frames_dir: Path
    frame_count: int
    start: float
    end: float
    recorded_at: datetime | None


@dataclass(frozen=True)
class Example:
    """One picture to learn from, with the Outcome of its Visit."""

    visit_id: str
    outcome: Outcome
    picture: Path
    taken_at: datetime | None


def read_labeled_visits(dataset: Path) -> list[LabeledVisit]:
    """Every labeled Visit in the manifest under `dataset`; none if there is no manifest."""
    manifest = dataset / "manifest.csv"
    if not manifest.exists():
        return []
    with manifest.open(newline="") as rows:
        return [
            LabeledVisit(
                id=row["visit_id"],
                outcome=Outcome(row["outcome"]),
                frames_dir=dataset / row["frames_dir"],
                frame_count=int(row["frame_count"]),
                start=float(row["start_seconds"]),
                end=float(row["end_seconds"]),
                recorded_at=datetime.fromisoformat(row["recorded_at"])
                if row["recorded_at"]
                else None,
            )
            for row in csv.DictReader(rows)
        ]


def surface_examples(visits: Iterable[LabeledVisit]) -> list[Example]:
    """The last frame of each Visit: the litter surface after the Cat has left."""
    return [_example(v, v.frame_count - 1) for v in visits if v.frame_count > 0]


def stance_examples(visits: Iterable[LabeledVisit], per_visit: int) -> list[Example]:
    """Up to `per_visit` evenly spread frames from the middle half of each Visit."""
    examples = []
    for visit in visits:
        count = visit.frame_count
        if count == 0:
            continue
        first, last = count // 4, count - 1 - count // 4
        if per_visit == 1:
            picked = [(first + last) // 2]
        else:
            picked = np.linspace(first, last, per_visit).round().astype(int).tolist()
        examples.extend(_example(visit, index) for index in sorted(set(picked)))
    return examples


def is_validation(visit_id: str, fraction: float) -> bool:
    """Whether Visit `visit_id` is held out for validation; about `fraction` of Visits are."""
    digest = hashlib.sha256(visit_id.encode()).digest()
    return int.from_bytes(digest[:4]) / 2**32 < fraction


def split(examples: Sequence[Example], fraction: float) -> tuple[list[Example], list[Example]]:
    """`examples` as (training, validation), holding out about `fraction` of the Visits."""
    validation = [e for e in examples if is_validation(e.visit_id, fraction)]
    training = [e for e in examples if not is_validation(e.visit_id, fraction)]
    return training, validation


def _example(visit: LabeledVisit, index: int) -> Example:
    """Frame `index` (from 0) of `visit`, with its time spread evenly over the Visit."""
    taken_at = None
    if visit.recorded_at is not None:
        along = index / (visit.frame_count - 1) if visit.frame_count > 1 else 0.0
        offset = visit.start + (visit.end - visit.start) * along
        taken_at = visit.recorded_at + timedelta(seconds=offset)
    picture = visit.frames_dir / frame_name(index + 1)
    return Example(visit.id, visit.outcome, picture, taken_at)
