"""Build tiny fake MP4 files for tests: just the boxes the readers look at."""

import struct
from datetime import UTC, datetime

MP4_EPOCH = datetime(1904, 1, 1, tzinfo=UTC)


def box(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", 8 + len(body)) + kind + body


def fake_mp4(created: datetime | None = None, *, version: int = 0, payload: bytes = b"") -> bytes:
    seconds = int((created - MP4_EPOCH).total_seconds()) if created else 0
    if version == 0:
        mvhd = bytes([0, 0, 0, 0]) + struct.pack(">II", seconds, seconds) + bytes(88)
    else:
        mvhd = bytes([1, 0, 0, 0]) + struct.pack(">QQ", seconds, seconds) + bytes(88)
    return (
        box(b"ftyp", b"isom" + bytes(4)) + box(b"moov", box(b"mvhd", mvhd)) + box(b"mdat", payload)
    )
