"""Record the live Visit going on to a local MP4, then save it in the Private Data Store.

Saved Visits wait for labeling (`make label`), so every Visit adds training data. After each
save the store is kept under `visits.max_store_gb`, on a background thread so the watcher
loop does not wait for it.
"""

import logging
import shutil
import tempfile
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from catpoop.config import VisitSettings
from catpoop.domain import Frame
from catpoop.visits.add_visit import save_clip_as_visit
from catpoop.visits.clip_writer import ClipWriter
from catpoop.visits.retention import prune_clips
from catpoop.visits.store import Visit
from catpoop.watcher.background_task import BackgroundTask

log = logging.getLogger(__name__)


class LiveVisitRecorder:
    """Writes one Visit at a time; frames are timed from the first one."""

    def __init__(
        self, private_data_store: Path, settings: VisitSettings, temp_folder: Path | None = None
    ) -> None:
        """Save to `private_data_store`; record in `temp_folder` (default: the system's)."""
        self._store = private_data_store
        self._settings = settings
        self._temp_folder = temp_folder
        self._writer: ClipWriter | None = None
        self._first: datetime | None = None
        self._pruning = BackgroundTask(self._prune, "pruning the Private Data Store")

    @property
    def recording(self) -> bool:
        """Whether a Visit is being recorded."""
        return self._writer is not None

    def start(self, frames: Iterable[Frame]) -> None:
        """Start a new clip with `frames`, the pictures from just before the Visit started."""
        self.discard()
        if self._temp_folder:
            self._temp_folder.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="catpoop-live-", dir=self._temp_folder))
        self._writer = ClipWriter(folder / "live.mp4")
        self._first = None
        for frame in frames:
            self.add(frame)

    def add(self, frame: Frame) -> None:
        """Add `frame` to the clip, if one is being recorded."""
        if self._writer is None:
            return
        if self._first is None:
            self._first = frame.taken_at
        self._writer.add((frame.taken_at - self._first).total_seconds(), frame.image)

    def save(self, now: datetime) -> Visit:
        """Finish the clip, save it as a Visit and prune; raises `OSError` or `VideoError`."""
        writer, first = self._writer, self._first
        if writer is None:
            raise RuntimeError("no Visit is being recorded")
        self._writer = None
        try:
            writer.close()
            name = f"live-{(first or now).strftime('%Y%m%dT%H%M%S%z')}.mp4"
            clip = writer.path.replace(writer.path.with_name(name))
            visit = save_clip_as_visit(
                clip, self._store, self._settings, now, source="live", recorded=first
            )
        finally:
            shutil.rmtree(writer.path.parent, ignore_errors=True)
        self._pruning.request()
        return visit

    def wait_for_prune(self, timeout: float | None = None) -> bool:
        """Wait for a prune going on to finish; False if `timeout` seconds passed first."""
        return self._pruning.wait(timeout)

    def _prune(self) -> None:
        try:
            prune_clips(self._store, int(self._settings.max_store_gb * 1e9))
        except OSError as error:
            log.error("could not keep the store under its size limit: %s", error)

    def discard(self) -> None:
        """Drop the clip being recorded, if any."""
        if self._writer is not None:
            self._writer.close()
            shutil.rmtree(self._writer.path.parent, ignore_errors=True)
            self._writer = None
