import pytest
from fake_video import write_clip
from PIL import Image

from catpoop.visits.video import VideoError, clip_seconds, read_frames, save_jpeg


def brightness(frames):
    return [(seconds, round(float(image.mean()) / 10)) for seconds, image in frames]


def test_reads_every_frame_as_rgb(tmp_path):
    clip = write_clip(tmp_path / "c.mp4", [0, 100, 200, 250])
    frames = list(read_frames(clip, every_seconds=0))
    assert [s for s, _ in frames] == [0, 0.25, 0.5, 0.75]
    assert frames[0][1].shape == (48, 64, 3)
    assert brightness(frames)[2] == (0.5, 20)


def test_reads_one_frame_per_interval(tmp_path):
    clip = write_clip(tmp_path / "c.mp4", list(range(0, 240, 10)))
    assert [s for s, _ in read_frames(clip, every_seconds=1)] == [0, 1, 2, 3, 4, 5]


def test_reads_only_a_span(tmp_path):
    clip = write_clip(tmp_path / "c.mp4", list(range(0, 240, 10)))
    assert [s for s, _ in read_frames(clip, 0.5, start=2, end=3.5)] == [2, 2.5, 3, 3.5]


def test_clip_length(tmp_path):
    assert clip_seconds(write_clip(tmp_path / "c.mp4", [0] * 10)) == pytest.approx(2.5)


def test_broken_clip_is_an_error(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    with pytest.raises(VideoError):
        list(read_frames(bad, 1))


def test_saves_jpeg(tmp_path):
    clip = write_clip(tmp_path / "c.mp4", [120])
    ((_, image),) = read_frames(clip, 1)
    save_jpeg(image, tmp_path / "f" / "frame_0001.jpg")
    with Image.open(tmp_path / "f" / "frame_0001.jpg") as saved:
        assert saved.format == "JPEG"
        assert saved.size == (64, 48)
