import io
import json
import tarfile
import zipfile
from datetime import UTC, datetime

import pytest

from catpoop.history.archive import archive_clips

WHEN = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
FILES = {
    "Takeout/Nest/cam/event-1.mp4": b"one",
    "Takeout/Nest/cam/event-1.json": json.dumps({"startTime": "2026-03-04T05:06:07Z"}).encode(),
    "Takeout/Nest/cam/event-2.MP4": b"two",
    "Takeout/Nest/cam/event-2.MP4.json": json.dumps({"note": "x"}).encode(),
    "Takeout/Nest/cam/event-1.jpg": b"jpg",
    "Takeout/archive_browser.html": b"<html>",
}


def read_all(path, source="takeout"):
    return {
        c.origin: (c.name, c.open().read(), c.recorded_at, c.metadata, c.source)
        for c in archive_clips(path, source)
    }


def check(found, prefix):
    assert set(found) == {
        f"{prefix}Takeout/Nest/cam/event-1.mp4",
        f"{prefix}Takeout/Nest/cam/event-2.MP4",
    }
    name, data, recorded_at, metadata, source = found[f"{prefix}Takeout/Nest/cam/event-1.mp4"]
    assert (name, data, recorded_at, source) == ("event-1.mp4", b"one", WHEN, "takeout")
    assert metadata == {"startTime": "2026-03-04T05:06:07Z"}
    name, data, recorded_at, metadata, _ = found[f"{prefix}Takeout/Nest/cam/event-2.MP4"]
    assert (name, data, recorded_at, metadata) == ("event-2.MP4", b"two", None, {"note": "x"})


def test_zip(tmp_path):
    path = tmp_path / "takeout-001.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in FILES.items():
            archive.writestr(name, data)
    check(read_all(path), "takeout-001.zip!")


@pytest.mark.parametrize("suffix", [".tgz", ".tar.gz", ".tar"])
def test_tar(tmp_path, suffix):
    path = tmp_path / f"takeout-001{suffix}"
    with tarfile.open(path, "w") if suffix == ".tar" else tarfile.open(path, "w:gz") as archive:
        for name, data in FILES.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    check(read_all(path), f"takeout-001{suffix}!")


def test_folder(tmp_path):
    root = tmp_path / "export"
    for name, data in FILES.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(data)
    check(read_all(root), "export/")


def test_bad_sidecar_is_ignored(tmp_path):
    root = tmp_path / "clips"
    root.mkdir()
    (root / "a.mp4").write_bytes(b"a")
    (root / "a.json").write_text("{not json")
    (clip,) = archive_clips(root, "folder")
    assert clip.metadata == {}


def test_unknown_file_type_is_an_error(tmp_path):
    path = tmp_path / "export.rar"
    path.write_bytes(b"")
    with pytest.raises(ValueError, match="rar"):
        list(archive_clips(path, "takeout"))
