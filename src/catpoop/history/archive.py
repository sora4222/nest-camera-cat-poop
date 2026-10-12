"""Find MP4 clips, and the JSON sidecars next to them, in an export archive or folder.

Works on `.zip`, `.tgz`/`.tar.gz`/`.tar` and plain folders. A sidecar is `<clip>.json` or
`<clip name without .mp4>.json`. Archives are read twice (sidecars, then clips) so a big
`.tgz` is streamed rather than seeked.
"""

import json
import tarfile
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path, PurePosixPath
from typing import IO, Any

from catpoop.history.importer import HistoryClip
from catpoop.history.sidecar import sidecar_time

type _Entries = Iterator[tuple[str, Callable[[], IO[bytes]]]]
_MAX_SIDECAR_BYTES = 1 << 20


def _folder_entries(root: Path) -> _Entries:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path.relative_to(root).as_posix(), lambda path=path: path.open("rb")


def _zip_entries(path: Path) -> _Entries:
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if not info.is_dir():
                yield info.filename, lambda info=info: archive.open(info)


def _tar_entries(path: Path) -> _Entries:
    with tarfile.open(path, "r|*") as archive:
        for member in archive:
            if member.isfile():
                yield member.name, lambda member=member: _extract(archive, member)


def _extract(archive: tarfile.TarFile, member: tarfile.TarInfo) -> IO[bytes]:
    file = archive.extractfile(member)
    if file is None:
        raise ValueError(f"cannot read {member.name}")
    return file


def _entries(path: Path) -> tuple[Callable[[], _Entries], str]:
    """How to list `path`, and the prefix that turns a member name into an origin."""
    name = path.name.lower()
    if path.is_dir():
        return lambda: _folder_entries(path), f"{path.name}/"
    if name.endswith(".zip"):
        return lambda: _zip_entries(path), f"{path.name}!"
    if name.endswith((".tgz", ".tar.gz", ".tar")):
        return lambda: _tar_entries(path), f"{path.name}!"
    raise ValueError(f"{path.name}: not a folder, .zip, .tgz or .tar")


def _read_sidecar(open_file: Callable[[], IO[bytes]]) -> dict[str, Any]:
    with open_file() as file:
        data = file.read(_MAX_SIDECAR_BYTES + 1)
    if len(data) > _MAX_SIDECAR_BYTES:
        return {}
    try:
        parsed = json.loads(data)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _skip(name: str) -> bool:
    return PurePosixPath(name).name.startswith("._") or "__MACOSX/" in name


def archive_clips(path: Path, source: str) -> Iterator[HistoryClip]:
    """Every MP4 in the archive or folder at `path`, labelled with `source`."""
    entries, prefix = _entries(path)
    sidecars = {
        name.lower(): _read_sidecar(open_file)
        for name, open_file in entries()
        if name.lower().endswith(".json") and not _skip(name)
    }
    for name, open_file in entries():
        lower = name.lower()
        if not lower.endswith(".mp4") or _skip(name):
            continue
        metadata = sidecars.get(f"{lower}.json") or sidecars.get(f"{lower[:-4]}.json") or {}
        yield HistoryClip(
            source=source,
            origin=prefix + name,
            name=PurePosixPath(name).name,
            open=open_file,
            recorded_at=sidecar_time(metadata),
            metadata=metadata,
        )
