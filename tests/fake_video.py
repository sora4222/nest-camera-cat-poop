"""Write tiny real MP4 clips for tests: one flat grey frame per brightness value."""

from pathlib import Path

import av
import numpy as np

FPS = 4
WIDTH, HEIGHT = 64, 48


def write_clip(path: Path, brightness: list[int], fps: int = FPS) -> Path:
    """An MP4 at `fps` whose frame `i` is filled with `brightness[i]`."""
    with av.open(str(path), "w") as container:
        stream = container.add_stream("mpeg4", rate=fps)
        stream.width, stream.height, stream.pix_fmt = WIDTH, HEIGHT, "yuv420p"
        for value in brightness:
            pixels = np.full((HEIGHT, WIDTH, 3), value, np.uint8)
            container.mux(stream.encode(av.VideoFrame.from_ndarray(pixels, format="rgb24")))
        container.mux(stream.encode())
    return path
