from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pytest

from catpoop.domain import Frame
from catpoop.parts.onnx_detector import COCO_LABELS, OnnxDetector

NOW = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)


@dataclass
class Port:
    name: str
    shape: list[Any] = field(default_factory=list)
    type: str = "tensor(float)"


class FakeSession:
    """Answers like a TF Object Detection API model exported with tf2onnx."""

    def __init__(self, input_shape=(1, None, None, 3), input_type="tensor(uint8)"):
        self.input = Port("input_tensor", list(input_shape), input_type)
        self.fed: dict[str, np.ndarray] = {}

    def get_inputs(self):
        return [self.input]

    def get_outputs(self):
        # Zoo models name outputs with a `:0` suffix and in any order.
        names = ["num_detections:0", "detection_scores:0", "detection_classes:0"]
        return [Port(name) for name in [*names, "detection_boxes:0"]]

    def run(self, output_names, feed):
        assert output_names is None
        self.fed = feed
        boxes = [[0.1, 0.2, 0.5, 0.6], [0.0, 0.0, 1.0, 1.0], [0.3, 0.3, 0.4, 0.4], [0, 0, 0, 0]]
        return [
            np.array([3.0], np.float32),
            np.array([[0.9, 0.8, 0.3, 0.95]], np.float32),
            np.array([[17.0, 62.0, 18.0, 18.0]], np.float32),
            np.array([boxes], np.float32),
        ]


def frame(height=6, width=8) -> Frame:
    return Frame(NOW, np.zeros((height, width, 3), np.uint8))


def test_finds_wanted_labels_above_the_minimum_score():
    detector = OnnxDetector(FakeSession(), COCO_LABELS, min_score=0.5)
    # Class 62 (chair) is not wanted, the dog is under the score, and row 4 is padding.
    [found] = detector.detect(frame())
    assert found.label == "cat"
    assert found.score == pytest.approx(0.9)
    assert found.box == pytest.approx((0.2, 0.1, 0.6, 0.5))


def test_lower_minimum_score_keeps_more():
    detector = OnnxDetector(FakeSession(), COCO_LABELS, min_score=0.2)
    assert [d.label for d in detector.detect(frame())] == ["cat", "dog"]


def test_feeds_the_frame_as_a_batch_of_one():
    session = FakeSession()
    OnnxDetector(session, COCO_LABELS).detect(frame())
    image = session.fed["input_tensor"]
    assert image.shape == (1, 6, 8, 3)
    assert image.dtype == np.uint8


def test_resizes_to_a_fixed_model_size():
    session = FakeSession(input_shape=(1, 4, 4, 3))
    pixels = np.arange(6 * 8 * 3, dtype=np.uint8).reshape(6, 8, 3)
    OnnxDetector(session, COCO_LABELS).detect(Frame(NOW, pixels))
    image = session.fed["input_tensor"]
    assert image.shape == (1, 4, 4, 3)
    assert (image[0, 0, 0] == pixels[0, 0]).all()


def test_float_models_get_float_pixels():
    session = FakeSession(input_type="tensor(float)")
    OnnxDetector(session, COCO_LABELS).detect(frame())
    assert session.fed["input_tensor"].dtype == np.float32
