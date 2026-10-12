"""Write `dataset/manifest.csv`: one row per labeled Visit, for `tf.data` and people."""

import csv
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from catpoop.visits.store import Visit

COLUMNS = [
    "visit_id",
    "outcome",
    "frames_dir",
    "frame_count",
    "clip",
    "start_seconds",
    "end_seconds",
    "recorded_at",
    "source",
    "labeled_at",
]
"""`frames_dir` is relative to the dataset folder, `clip` to the Private Data Store."""


def write_manifest(path: Path, visits: Iterable["Visit"]) -> None:
    """Replace the manifest at `path` with a row for each labeled Visit in `visits`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.part")
    with temp.open("w", newline="") as out:
        writer = csv.DictWriter(out, COLUMNS)
        writer.writeheader()
        for visit in visits:
            if visit.outcome is None:
                continue
            writer.writerow(
                {
                    "visit_id": visit.id,
                    "outcome": visit.outcome.value,
                    "frames_dir": f"{visit.outcome.value}/{visit.id}",
                    "frame_count": visit.frames,
                    "clip": f"history/clips/{visit.clip}.mp4",
                    "start_seconds": visit.start,
                    "end_seconds": visit.end,
                    "recorded_at": visit.recorded_at or "",
                    "source": visit.source,
                    "labeled_at": visit.labeled_at or "",
                }
            )
    temp.replace(path)
