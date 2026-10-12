"""History importer `portability`: clips from the Google Data Portability API (`nest.camera_event`).

Starts an export job (or resumes `job_id`), waits for it, downloads its archives into the
Private Data Store, then reads the clips in them. Not offered in every country.
"""

import logging
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from catpoop.config import Config, ConfigError
from catpoop.history.archive import archive_clips
from catpoop.history.importer import HistoryClip
from catpoop.history.portability_api import PortabilityApi, PortabilityError
from catpoop.history.portability_http import PortabilityHttpApi
from catpoop.registry import DEFAULT, HISTORY_IMPORTER

log = logging.getLogger(__name__)


class PortabilityImporter:
    """Exports camera events through `api` and reads the clips in the archives."""

    def __init__(
        self,
        api: PortabilityApi,
        downloads: Path,
        *,
        resources: Sequence[str] = ("nest.camera_event",),
        start: datetime | None = None,
        end: datetime | None = None,
        job_id: str | None = None,
        poll_seconds: float = 60,
        max_wait_seconds: float = 24 * 60 * 60,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Keep downloaded archives in `downloads/<job id>/`."""
        self.api = api
        self.downloads = downloads
        self.resources = list(resources)
        self.start = start
        self.end = end
        self.job_id = job_id
        self.poll_seconds = poll_seconds
        self.max_wait_seconds = max_wait_seconds
        self.sleep = sleep

    def clips(self) -> Iterator[HistoryClip]:
        """Every clip in the export's archives."""
        job_id = self.job_id or self.api.initiate(self.resources, self.start, self.end)
        log.info("Data Portability job %s (resume with job_id)", job_id)
        for archive in self._download(job_id, self._wait(job_id)):
            yield from archive_clips(archive, "portability")

    def _wait(self, job_id: str) -> list[str]:
        waited = 0.0
        while True:
            state = self.api.state(job_id)
            if state.state == "COMPLETE":
                return state.urls
            if state.state != "IN_PROGRESS":
                raise PortabilityError(f"job {job_id} ended {state.state}")
            if waited >= self.max_wait_seconds:
                raise PortabilityError(f"job {job_id} still running; resume it later with job_id")
            self.sleep(self.poll_seconds)
            waited += self.poll_seconds

    def _download(self, job_id: str, urls: list[str]) -> list[Path]:
        folder = self.downloads / job_id
        folder.mkdir(parents=True, exist_ok=True)
        archives = []
        for number, url in enumerate(urls, start=1):
            archive = folder / f"part-{number:03}.zip"
            if not archive.exists():
                partial = archive.with_suffix(".zip.part")
                self.api.download(url, partial)
                partial.replace(archive)
            archives.append(archive)
        return archives


def _time_option(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        raise ConfigError(f"history portability: {value!r} is not an ISO time") from None


@DEFAULT.part(HISTORY_IMPORTER, "portability")
def _create(config: Config, options: Mapping[str, Any]) -> PortabilityImporter:
    downloads = config.paths.private_data_store / "history" / "downloads" / "portability"
    return PortabilityImporter(
        PortabilityHttpApi.from_env(),
        downloads,
        resources=options.get("resources", ["nest.camera_event"]),
        start=_time_option(options.get("start_time")),
        end=_time_option(options.get("end_time")),
        job_id=options.get("job_id"),
        poll_seconds=float(options.get("poll_seconds", 60)),
        max_wait_seconds=float(options.get("max_wait_seconds", 24 * 60 * 60)),
    )
