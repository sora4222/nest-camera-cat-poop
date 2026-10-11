"""Write RGB frames to an MP4 clip as they arrive, each at its own time (PyAV)."""

from fractions import Fraction
from pathlib import Path
from types import TracebackType
from typing import Any

import av
import numpy as np

_TIME_BASE = Fraction(1, 1000)


class ClipWriter:
    """An MP4 at `path`, written frame by frame; the size comes from the first frame.

    Nothing is written if no frame is added.
    """

    def __init__(self, path: Path, bit_rate: int = 2_000_000) -> None:
        """Write to `path` once the first frame arrives."""
        self.path = path
        self._bit_rate = bit_rate
        self._container: Any = None
        self._stream: Any = None
        self._last_pts = -1

    def add(self, seconds: float, image: np.ndarray) -> None:
        """Add `image` at `seconds` from the start; frames not after the last one are skipped."""
        pts = round(seconds / _TIME_BASE)
        if pts <= self._last_pts:
            return
        pixels = np.asarray(image)
        height, width = pixels.shape[0] // 2 * 2, pixels.shape[1] // 2 * 2
        if self._stream is None:
            self._open(width, height)
        frame = av.VideoFrame.from_ndarray(
            np.ascontiguousarray(pixels[:height, :width]), format="rgb24"
        )
        frame.pts, frame.time_base = pts, _TIME_BASE
        self._container.mux(self._stream.encode(frame))
        self._last_pts = pts

    def close(self) -> None:
        """Finish the clip."""
        if self._container is None:
            return
        self._container.mux(self._stream.encode())
        self._container.close()
        self._container = None

    def __enter__(self) -> "ClipWriter":
        """Use as a `with` block that closes the clip."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the clip."""
        self.close()

    def _open(self, width: int, height: int) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._container = av.open(str(self.path), "w")
        stream = self._container.add_stream("mpeg4", rate=30)
        stream.width, stream.height, stream.pix_fmt = width, height, "yuv420p"
        stream.time_base = stream.codec_context.time_base = _TIME_BASE
        stream.bit_rate = self._bit_rate
        self._stream = stream
