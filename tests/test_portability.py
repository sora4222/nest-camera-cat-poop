import zipfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from catpoop.history.portability import PortabilityImporter
from catpoop.history.portability_api import ArchiveState, PortabilityError

START = datetime(2026, 1, 1, tzinfo=UTC)


class FakeApi:
    def __init__(self, states: list[ArchiveState], archives: dict[str, list[str]]) -> None:
        self.states = states
        self.archives = archives
        self.initiated: list[tuple[list[str], datetime | None, datetime | None]] = []
        self.downloaded: list[str] = []

    def initiate(self, resources: Sequence[str], start, end) -> str:
        self.initiated.append((list(resources), start, end))
        return "job-1"

    def state(self, job_id: str) -> ArchiveState:
        assert job_id == "job-1"
        return self.states.pop(0)

    def download(self, url: str, to: Path) -> None:
        self.downloaded.append(url)
        with zipfile.ZipFile(to, "w") as archive:
            for name in self.archives[url]:
                archive.writestr(name, b"x")


def importer(api: FakeApi, tmp_path: Path, **kwargs) -> PortabilityImporter:
    return PortabilityImporter(api, tmp_path / "downloads", sleep=lambda _: None, **kwargs)


def test_exports_waits_downloads_and_reads_clips(tmp_path):
    api = FakeApi(
        [ArchiveState("IN_PROGRESS"), ArchiveState("COMPLETE", ["https://a", "https://b"])],
        {"https://a": ["nest/a.mp4"], "https://b": ["nest/b.mp4", "nest/b.json"]},
    )
    clips = list(importer(api, tmp_path, start=START).clips())
    assert api.initiated == [(["nest.camera_event"], START, None)]
    assert [(c.source, c.origin) for c in clips] == [
        ("portability", "part-001.zip!nest/a.mp4"),
        ("portability", "part-002.zip!nest/b.mp4"),
    ]
    assert (tmp_path / "downloads" / "job-1" / "part-002.zip").exists()


def test_resumes_a_job_without_downloading_again(tmp_path):
    complete = ArchiveState("COMPLETE", ["https://a"])
    api = FakeApi([complete, complete], {"https://a": ["nest/a.mp4"]})
    list(importer(api, tmp_path).clips())
    clips = list(importer(api, tmp_path, job_id="job-1").clips())
    assert len(api.initiated) == 1
    assert api.downloaded == ["https://a"]
    assert len(clips) == 1


@pytest.mark.parametrize("state", ["FAILED", "CANCELLED"])
def test_failed_job_is_an_error(tmp_path, state):
    api = FakeApi([ArchiveState(state)], {})
    with pytest.raises(PortabilityError, match=state):
        list(importer(api, tmp_path).clips())


def test_gives_up_after_the_wait_limit(tmp_path):
    api = FakeApi([ArchiveState("IN_PROGRESS")] * 5, {})
    with pytest.raises(PortabilityError, match="job-1"):
        list(importer(api, tmp_path, poll_seconds=60, max_wait_seconds=120).clips())
