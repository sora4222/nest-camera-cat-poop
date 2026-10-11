from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from catpoop.config import Config, ConfigError
from catpoop.domain import Frame
from catpoop.registry import DETECTOR, default_registry

onnx = pytest.importorskip("onnx")
pytest.importorskip("onnxruntime")
from onnx import TensorProto, helper  # noqa: E402


def tiny_detector(path: Path) -> Path:
    """An ONNX model shaped like a TF detector that always finds a cat and a person."""
    outputs = {
        "detection_boxes": np.array([[[0.1, 0.2, 0.5, 0.6], [0.0, 0.0, 1.0, 1.0]]], np.float32),
        "detection_classes": np.array([[17.0, 1.0]], np.float32),
        "detection_scores": np.array([[0.9, 0.4]], np.float32),
        "num_detections": np.array([2.0], np.float32),
    }
    nodes = [
        helper.make_node("Constant", [], [name], value=onnx.numpy_helper.from_array(value))
        for name, value in outputs.items()
    ]
    graph = helper.make_graph(
        nodes,
        "tiny_detector",
        [helper.make_tensor_value_info("input_tensor", TensorProto.UINT8, [1, "h", "w", 3])],
        [
            helper.make_tensor_value_info(name, TensorProto.FLOAT, list(value.shape))
            for name, value in outputs.items()
        ],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 9
    onnx.save(model, path)
    return path


def config(store: Path, **detector) -> Config:
    return Config.model_validate(
        {
            "parts": {
                "camera": "nest",
                "detector": "onnx",
                "event_rules": "standard",
                "event_log": "memory",
                "presence": "off",
                "communications": "standard",
            },
            "paths": {"private_data_store": str(store)},
            "detector": detector,
        }
    )


def create(cfg: Config):
    return default_registry().create(DETECTOR, "onnx", cfg, cfg.part_options("detector"))


def test_runs_the_model_named_in_config(tmp_path):
    tiny_detector(tmp_path / "pets.onnx")
    detector = create(config(tmp_path, model="pets.onnx", runtime="cpu"))
    frame = Frame(datetime(2026, 1, 1, tzinfo=UTC), np.zeros((6, 8, 3), np.uint8))
    assert [d.label for d in detector.detect(frame)] == ["cat"]


def test_labels_and_minimum_score_come_from_config(tmp_path):
    tiny_detector(tmp_path / "pets.onnx")
    cfg = config(tmp_path, model="pets.onnx", min_score=0.3, labels={"1": "human", "17": "cat"})
    frame = Frame(datetime(2026, 1, 1, tzinfo=UTC), np.zeros((6, 8, 3), np.uint8))
    assert [d.label for d in create(cfg).detect(frame)] == ["cat", "human"]


def test_absolute_model_path_is_used_as_is(tmp_path):
    model = tiny_detector(tmp_path / "pets.onnx")
    create(config(tmp_path / "elsewhere", model=str(model)))


def test_missing_model_option_is_a_config_error(tmp_path):
    with pytest.raises(ConfigError, match=r"detector\.model"):
        create(config(tmp_path))


def test_missing_model_file_is_a_config_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        create(config(tmp_path, model="nope.onnx"))


def test_unknown_runtime_is_a_config_error(tmp_path):
    tiny_detector(tmp_path / "pets.onnx")
    with pytest.raises(ConfigError, match=r"detector\.runtime"):
        create(config(tmp_path, model="pets.onnx", runtime="tpu"))
