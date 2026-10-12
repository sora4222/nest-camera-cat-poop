"""Read frames from an MP4 clip (PyAV) and save them as JPEG pictures (Pillow)."""

from collections.abc import Iterator
from pathlib import Path

import av
import numpy as np
from PIL import Image

_EPSILON = 1e-6


class VideoError(Exception):
    """The clip cannot be read."""


def clip_seconds(path: Path) -> float:
    """How long the clip at `path` is."""
    try:
        with av.open(str(path)) as container:
            if container.duration is not None:
                return container.duration / av.time_base
            stream = container.streams.video[0]
            if stream.duration is not None and stream.time_base is not None:
                return float(stream.duration * stream.time_base)
    except (av.FFmpegError, IndexError) as error:
        raise VideoError(f"{path}: {error}") from None
    return max((seconds for seconds, _ in read_frames(path, 0)), default=0.0)


def read_frames(
    path: Path, every_seconds: float, start: float = 0.0, end: float | None = None
) -> Iterator[tuple[float, np.ndarray]]:
    """`(seconds, RGB array)` for one frame every `every_seconds` from `start` to `end`.

    `every_seconds` 0 gives every frame.
    """
    try:
        with av.open(str(path)) as container:
            stream = container.streams.video[0]
            origin = 0.0
            if stream.start_time is not None and stream.time_base is not None:
                origin = float(stream.start_time * stream.time_base)
            if start > 0 and stream.time_base is not None:
                container.seek(int((start + origin) / stream.time_base), stream=stream)
            wanted = start
            for frame in container.decode(stream):
                if frame.time is None:
                    continue
                seconds = float(frame.time) - origin
                if end is not None and seconds > end + _EPSILON:
                    return
                if seconds + _EPSILON < wanted:
                    continue
                yield seconds, frame.to_ndarray(format="rgb24")
                if every_seconds <= 0:
                    continue
                while wanted <= seconds + _EPSILON:
                    wanted += every_seconds
    except (av.FFmpegError, IndexError) as error:
        raise VideoError(f"{path}: {error}") from None


def save_jpeg(image: np.ndarray, path: Path, quality: int = 90) -> None:
    """Write the RGB array `image` to `path` as a JPEG, making its folder."""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image).save(path, "JPEG", quality=quality)
