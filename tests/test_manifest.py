import csv

from catpoop.domain import Outcome
from catpoop.visits.manifest import COLUMNS, write_manifest
from catpoop.visits.store import Visit


def test_only_labeled_visits_are_written(tmp_path):
    path = tmp_path / "dataset" / "manifest.csv"
    visits = [
        Visit("a" * 16 + "-0000000", "a" * 64, 0, 3, None, frames=6, outcome=Outcome.NOTHING),
        Visit("b" * 16 + "-0000000", "b" * 64, 0, 3, None),
    ]
    write_manifest(path, visits)
    with path.open() as manifest:
        reader = csv.DictReader(manifest)
        rows = list(reader)
    assert reader.fieldnames == COLUMNS
    assert [row["outcome"] for row in rows] == ["nothing"]
    assert rows[0]["recorded_at"] == ""
