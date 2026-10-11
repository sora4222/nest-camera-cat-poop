"""Model inputs made the same way in training and on the server: pictures and time of day.

Only numpy and Pillow, so the server never needs TensorFlow.
"""

import math
from datetime import datetime, tzinfo
from pathlib import Path

import numpy as np
from PIL import Image

from catpoop.domain import Outcome

CLASSES = (Outcome.PEE, Outcome.POOP, Outcome.NOTHING)
"""The Outcome of each model output, in order."""

TIME_FEATURES = 3
"""Length of `time_features`."""

_DAY_SECONDS = 24 * 60 * 60


def prepare_image(image: np.ndarray, size: int) -> np.ndarray:
    """The RGB array `image` resized to `size` x `size`, as float32 pixels from 0 to 255."""
    resized = Image.fromarray(np.asarray(image, np.uint8)).resize(
        (size, size), Image.Resampling.BILINEAR
    )
    return np.asarray(resized, np.float32)


def load_image(path: Path, size: int) -> np.ndarray:
    """The picture at `path`, as `prepare_image` gives it."""
    with Image.open(path) as picture:
        return prepare_image(np.asarray(picture.convert("RGB")), size)


def time_features(at: datetime | None, zone: tzinfo | None = None) -> np.ndarray:
    """Time of day as `[sin, cos, known]`, so 23:59 is next to 00:00.

    The clock is read in `zone` (default: this machine's). An unknown time gives zeros.
    """
    if at is None:
        return np.zeros(TIME_FEATURES, np.float32)
    local = at.astimezone(zone)
    seconds = local.hour * 3600 + local.minute * 60 + local.second
    angle = 2 * math.pi * seconds / _DAY_SECONDS
    return np.array([math.sin(angle), math.cos(angle), 1.0], np.float32)
