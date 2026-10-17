"""Keep Visits in the Private Data Store: their records, their frames and the dataset.

Layout under the store:

- `visits/<visit id>.json`: the Visit record (clip, span, Outcome once labeled).
- `visits/frames/<visit id>/frame_0001.jpg`: frames of a Visit not labeled yet.
- `visits/scanned/<clip sha256>`: the clip has been cut into Visits.
- `dataset/<pee|poop|nothing>/<visit id>/frame_0001.jpg`: frames of labeled Visits.
- `dataset/manifest.csv`: one row per labeled Visit (see `manifest.py`).
"""

import json
import re
import shutil
from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path

import numpy as np

from catpoop.domain import Outcome
from catpoop.visits.manifest import write_manifest
from catpoop.visits.video import save_jpeg

_ID = re.compile(r"^[0-9a-f]{16}-\d{7}$")


def visit_id(clip: str, start: float) -> str:
    """The id of the Visit starting `start` seconds into the clip with hash `clip`."""
    return f"{clip[:16]}-{round(start * 1000):07d}"


def frame_name(number: int) -> str:
    """File name of frame `number`, counting from 1."""
    return f"frame_{number:04d}.jpg"


@dataclass(frozen=True)
class Visit:
    """One Visit cut from a history clip."""

    id: str
    clip: str
    """sha256 of the original clip in `history/clips`."""
    start: float
    end: float
    recorded_at: str | None
    """When the clip was recorded (ISO 8601), if known."""
    source: str = "detector"
    """`detector` when cut by `cut-visits`, `manual` when added by hand, `live` from the watcher."""
    frames: int = 0
    outcome: Outcome | None = None
    labeled_at: str | None = None


class VisitStore:
    """Visits, their frames and the labeled dataset under one Private Data Store."""

    def __init__(self, private_data_store: Path) -> None:
        """Use the Private Data Store at `private_data_store`."""
        self.visits = private_data_store / "visits"
        self.dataset = private_data_store / "dataset"

    def add(self, visit: Visit, images: Iterable[np.ndarray]) -> Visit:
        """Save `visit` with `images` as its frames; one with an Outcome goes to the dataset.

        A Visit already saved under the same id is replaced, frames and all.
        """
        folder = self._frames_folder(visit)
        temp = folder.with_name(f".{folder.name}.part")
        shutil.rmtree(temp, ignore_errors=True)
        count = 0
        for count, image in enumerate(images, start=1):
            save_jpeg(image, temp / frame_name(count))
        temp.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(folder, ignore_errors=True)
        temp.replace(folder)
        existing = self.get(visit.id)
        if existing is not None and self._frames_folder(existing) != folder:
            shutil.rmtree(self._frames_folder(existing), ignore_errors=True)
        saved = replace(visit, frames=count)
        self._write(saved)
        if saved.outcome is not None:
            self._write_manifest()
        return saved

    def get(self, id: str) -> Visit | None:
        """The Visit called `id`, or None."""
        if not _ID.match(id):
            return None
        path = self.visits / f"{id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        outcome = data.pop("outcome")
        return Visit(**data, outcome=Outcome(outcome) if outcome else None)

    def all(self) -> list[Visit]:
        """Every Visit, oldest first."""
        found = (self.get(path.stem) for path in self.visits.glob("*.json"))
        return sorted(
            (v for v in found if v is not None),
            key=lambda v: (v.recorded_at or "", v.clip, v.start),
        )

    def unlabeled(self) -> list[Visit]:
        """Visits with no Outcome yet, oldest first."""
        return [v for v in self.all() if v.outcome is None]

    def visits_of(self, clip: str) -> list[Visit]:
        """The Visits of `clip`, read fresh from disk by their id prefix; earliest first."""
        found = (self.get(path.stem) for path in self.visits.glob(f"{clip[:16]}-*.json"))
        return sorted((v for v in found if v is not None and v.clip == clip), key=lambda v: v.start)

    def frame_path(self, id: str, number: int) -> Path | None:
        """Frame `number` (from 1) of Visit `id`, or None if there is no such frame."""
        visit = self.get(id)
        if visit is None or not 1 <= number <= visit.frames:
            return None
        return self._frames_folder(visit) / frame_name(number)

    def label(self, id: str, outcome: Outcome, now: datetime) -> Visit:
        """Give Visit `id` its Outcome and move its frames into the dataset."""
        visit = self.get(id)
        if visit is None:
            raise KeyError(id)
        labeled = replace(visit, outcome=outcome, labeled_at=now.isoformat())
        target = self._frames_folder(labeled)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._frames_folder(visit).replace(target)
        self._write(labeled)
        self._write_manifest()
        return labeled

    def remove_unlabeled(self, clip: str) -> int:
        """Forget the unlabeled Visits of `clip` and that it was cut; return bytes freed.

        Labeled Visits stay.
        """
        freed = 0
        for visit in self.visits_of(clip):
            if visit.outcome is None:
                record = self.visits / f"{visit.id}.json"
                folder = self._frames_folder(visit)
                freed += record.stat().st_size + sum(f.stat().st_size for f in folder.glob("*"))
                shutil.rmtree(folder, ignore_errors=True)
                record.unlink()
        (self.visits / "scanned" / clip).unlink(missing_ok=True)
        return freed

    def is_scanned(self, clip: str) -> bool:
        """Whether `clip` has been cut into Visits."""
        return (self.visits / "scanned" / clip).exists()

    def mark_scanned(self, clip: str) -> None:
        """Remember that `clip` has been cut into Visits."""
        (self.visits / "scanned").mkdir(parents=True, exist_ok=True)
        (self.visits / "scanned" / clip).touch()

    def _frames_folder(self, visit: Visit) -> Path:
        if visit.outcome is None:
            return self.visits / "frames" / visit.id
        return self.dataset / visit.outcome.value / visit.id

    def _write(self, visit: Visit) -> None:
        self.visits.mkdir(parents=True, exist_ok=True)
        path = self.visits / f"{visit.id}.json"
        temp = path.with_name(f".{path.name}.part")
        temp.write_text(json.dumps(asdict(visit), indent=2))
        temp.replace(path)

    def _write_manifest(self) -> None:
        write_manifest(self.dataset / "manifest.csv", self.all())
