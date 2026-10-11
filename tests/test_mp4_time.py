from datetime import UTC, datetime

from fake_mp4 import box, fake_mp4

from catpoop.history.mp4_time import mp4_creation_time

WHEN = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)


def write(tmp_path, data: bytes):
    path = tmp_path / "clip.mp4"
    path.write_bytes(data)
    return path


def test_reads_creation_time(tmp_path):
    assert mp4_creation_time(write(tmp_path, fake_mp4(WHEN))) == WHEN


def test_reads_64_bit_creation_time(tmp_path):
    assert mp4_creation_time(write(tmp_path, fake_mp4(WHEN, version=1))) == WHEN


def test_zero_time_means_unknown(tmp_path):
    assert mp4_creation_time(write(tmp_path, fake_mp4(None))) is None


def test_no_movie_header_means_unknown(tmp_path):
    data = box(b"ftyp", b"isom") + box(b"mdat", b"x")
    assert mp4_creation_time(write(tmp_path, data)) is None


def test_not_an_mp4_means_unknown(tmp_path):
    assert mp4_creation_time(write(tmp_path, b"hello")) is None
