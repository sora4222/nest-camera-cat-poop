"""Keep imported history clips in the Private Data Store, each with a record of its sources.

Layout under the store: `history/clips/<sha256>.mp4` (original bytes, unchanged) and
`history/clips/<sha256>.json` (recording time and every place the clip was found).
The same clip found twice is stored once.
"""

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from catpoop.history.importer import HistoryClip
from catpoop.history.mp4_time import mp4_creation_time


@dataclass(frozen=True)
class SavedClip:
    """Where a clip was stored and whether it was new."""

    path: Path
    sha256: str
    new: bool


class HistoryClipStore:
    """Writes clips into `<private data store>/history/clips`."""

    def __init__(self, private_data_store: Path) -> None:
        """Use the Private Data Store at `private_data_store`."""
        self.folder = private_data_store / "history" / "clips"

    def save(self, clip: HistoryClip, now: datetime) -> SavedClip:
        """Store `clip` unless it is already there, and record where it came from."""
        self.folder.mkdir(parents=True, exist_ok=True)
        temp, sha256 = self._copy_in(clip)
        path = self.folder / f"{sha256}.mp4"
        new = not path.exists()
        if new:
            temp.replace(path)
        else:
            temp.unlink()
        self._record(path.with_suffix(".json"), path, clip, now)
        return SavedClip(path, sha256, new)

    def _copy_in(self, clip: HistoryClip) -> tuple[Path, str]:
        digest = hashlib.sha256()
        handle, name = tempfile.mkstemp(dir=self.folder, prefix=".importing-", suffix=".part")
        with os.fdopen(handle, "wb") as out, clip.open() as source:
            while chunk := source.read(1 << 20):
                digest.update(chunk)
                out.write(chunk)
        return Path(name), digest.hexdigest()

    def _record(self, record_path: Path, clip_path: Path, clip: HistoryClip, now: datetime) -> None:
        record: dict[str, Any] = (
            json.loads(record_path.read_text()) if record_path.exists() else {"recorded_at": None}
        )
        changed = not record_path.exists()
        if record["recorded_at"] is None:
            recorded_at = clip.recorded_at or mp4_creation_time(clip_path)
            if recorded_at:
                record["recorded_at"] = recorded_at.isoformat()
                changed = True
        sources: list[dict[str, Any]] = record.setdefault("sources", [])
        if not any(s["source"] == clip.source and s["origin"] == clip.origin for s in sources):
            sources.append(
                {
                    "source": clip.source,
                    "origin": clip.origin,
                    "name": clip.name,
                    "imported_at": now.isoformat(),
                    "metadata": dict(clip.metadata),
                }
            )
            changed = True
        if not changed:
            return
        temp = record_path.with_name(f".{record_path.name}.part")
        temp.write_text(json.dumps(record, indent=2))
        temp.replace(record_path)
