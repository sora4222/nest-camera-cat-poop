"""Write tiny real MP4 clips for tests: one flat grey frame per brightness value."""

from pathlib import Path

import av
import numpy as np

FPS = 4
WIDTH, HEIGHT = 64, 48


def write_clip(path: Path, brightness: list[int], fps: int = FPS, first_frame: int = 0) -> Path:
    """An MP4 at `fps` whose frame `i` is filled with `brightness[i]`.

    `first_frame` > 0 starts the stream timeline late, as in a trimmed clip.
    """
    with av.open(str(path), "w") as container:
        stream = container.add_stream("mpeg4", rate=fps)
        stream.width, stream.height, stream.pix_fmt = WIDTH, HEIGHT, "yuv420p"
        for index, value in enumerate(brightness):
            pixels = np.full((HEIGHT, WIDTH, 3), value, np.uint8)
            frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            frame.pts = first_frame + index
            container.mux(stream.encode(frame))
        container.mux(stream.encode())
    return path
