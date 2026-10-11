"""Detector "onnx": a TensorFlow Object Detection API model exported to ONNX.

The model takes one RGB picture `[1, H, W, 3]` and gives `detection_boxes`
(`[ymin, xmin, ymax, xmax]` fractions), `detection_classes`, `detection_scores`
and `num_detections`, as SSD MobileNet and EfficientDet from the TF model zoo do.
"""

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from catpoop.config import Config, ConfigError
from catpoop.domain import Detection, Frame
from catpoop.onnx_session import RUNTIMES, open_session
from catpoop.registry import DEFAULT, DETECTOR

COCO_LABELS = {1: "person", 17: "cat", 18: "dog"}
"""Class ids of the TF model zoo COCO label map that matter here."""

_PORT_SUFFIX = re.compile(r":\d+$")


class OnnxDetector:
    """Runs an ONNX Runtime session and keeps the labelled classes above `min_score`."""

    def __init__(self, session: Any, labels: Mapping[int, str], min_score: float = 0.5) -> None:
        """`session` is an `onnxruntime.InferenceSession` (or a fake with the same methods)."""
        self._session = session
        self._labels = dict(labels)
        self._min_score = min_score
        self._input = session.get_inputs()[0]
        self._outputs = [_PORT_SUFFIX.sub("", port.name) for port in session.get_outputs()]

    def detect(self, frame: Frame) -> list[Detection]:
        """The Cat, Dog and people found in `frame`."""
        results = self._session.run(None, {self._input.name: self._prepare(frame.image)})
        out = dict(zip(self._outputs, results, strict=True))
        count = int(out["num_detections"][0])
        found = []
        for cls, score, (top, left, bottom, right) in zip(
            out["detection_classes"][0][:count].astype(int).tolist(),
            out["detection_scores"][0][:count].tolist(),
            out["detection_boxes"][0][:count].tolist(),
            strict=True,
        ):
            if cls in self._labels and score >= self._min_score:
                found.append(Detection(self._labels[cls], score, (left, top, right, bottom)))
        return found

    def _prepare(self, image: Any) -> np.ndarray:
        """`image` as the model's input: resized if its size is fixed, with one batch row."""
        pixels = np.asarray(image)
        _, height, width, _ = self._input.shape
        if isinstance(height, int) and isinstance(width, int):
            rows = np.arange(height) * pixels.shape[0] // height
            cols = np.arange(width) * pixels.shape[1] // width
            pixels = pixels[rows][:, cols]
        dtype = np.uint8 if self._input.type == "tensor(uint8)" else np.float32
        return pixels.astype(dtype)[None]


@DEFAULT.part(DETECTOR, "onnx")
def _create(config: Config, options: Mapping[str, Any]) -> OnnxDetector:
    if "model" not in options:
        raise ConfigError("detector.model: the .onnx file to use is missing")
    model = config.paths.private_data_store / Path(options["model"])
    if not model.is_file():
        raise ConfigError(f"detector.model: {model} not found")
    runtime = options.get("runtime", "auto")
    if runtime not in RUNTIMES:
        raise ConfigError(f"detector.runtime: use one of {', '.join(RUNTIMES)}")
    labels = {int(cls): label for cls, label in options.get("labels", COCO_LABELS).items()}
    return OnnxDetector(open_session(model, runtime), labels, options.get("min_score", 0.5))
