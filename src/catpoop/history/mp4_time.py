"""Read when an MP4 was recorded from its movie header (`moov/mvhd`), with no extra tools."""

import struct
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO

_MP4_EPOCH = datetime(1904, 1, 1, tzinfo=UTC)


def _boxes(file: BinaryIO, end: int) -> Iterator[tuple[bytes, int, int]]:
    """Yield (type, body start, body end) for each box from the current position to `end`."""
    while file.tell() + 8 <= end:
        start = file.tell()
        size, kind = struct.unpack(">I4s", file.read(8))
        header = 8
        if size == 1:
            extended = file.read(8)
            if len(extended) < 8:
                return
            (size,) = struct.unpack(">Q", extended)
            header = 16
        elif size == 0:
            size = end - start
        if size < header or start + size > end:
            return
        yield kind, start + header, start + size
        file.seek(start + size)


def mp4_creation_time(path: Path) -> datetime | None:
    """The creation time in the MP4 header, or None if it is missing, zero or unreadable."""
    with path.open("rb") as file:
        size = path.stat().st_size
        for kind, body, end in _boxes(file, size):
            if kind != b"moov":
                continue
            file.seek(body)
            for child, child_body, _ in _boxes(file, end):
                if child != b"mvhd":
                    continue
                file.seek(child_body)
                header = file.read(20)
                if len(header) < 12:
                    return None
                if header[0] == 1:
                    (seconds,) = struct.unpack(">Q", header[4:12])
                else:
                    (seconds,) = struct.unpack(">I", header[4:8])
                return _MP4_EPOCH + timedelta(seconds=seconds) if seconds else None
    return None
