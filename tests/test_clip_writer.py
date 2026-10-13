import numpy as np
import pytest

from catpoop.visits.clip_writer import ClipWriter
from catpoop.visits.video import clip_seconds, read_frames


def grey(value: int, height: int = 48, width: int = 64) -> np.ndarray:
    return np.full((height, width, 3), value, np.uint8)


def test_frames_land_at_their_own_times(tmp_path):
    path = tmp_path / "live.mp4"
    with ClipWriter(path) as clip:
        for seconds, value in [(0.0, 0), (0.3, 100), (1.0, 200)]:
            clip.add(seconds, grey(value))
    frames = list(read_frames(path, every_seconds=0))
    assert [round(s, 2) for s, _ in frames] == [0.0, 0.3, 1.0]
    assert round(float(frames[1][1].mean()) / 10) == 10


def test_frames_out_of_order_are_skipped(tmp_path):
    path = tmp_path / "live.mp4"
    with ClipWriter(path) as clip:
        clip.add(1.0, grey(0))
        clip.add(1.0, grey(50))
        clip.add(0.5, grey(50))
        clip.add(2.0, grey(100))
    assert len(list(read_frames(path, every_seconds=0))) == 2
    assert clip_seconds(path) == pytest.approx(1.0, abs=0.2)


def test_odd_sizes_are_trimmed_to_even(tmp_path):
    path = tmp_path / "live.mp4"
    with ClipWriter(path) as clip:
        clip.add(0, grey(0, 47, 63))
    [(_, image)] = read_frames(path, every_seconds=0)
    assert image.shape == (46, 62, 3)


def test_no_frames_writes_no_file(tmp_path):
    path = tmp_path / "live.mp4"
    with ClipWriter(path):
        pass
    assert not path.exists()
