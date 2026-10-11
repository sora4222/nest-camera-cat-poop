"""Tiny hand-made ONNX Outcome models for tests: the mean colour picks the Outcome.

A red picture scores Pee, green Poop and blue Nothing. The Outcome Guess model also
adds 1000 to Poop times the `sin` of the time of day, so 6am always guesses Poop.
"""

from pathlib import Path

import numpy as np
import pytest

from catpoop.outcome.model_files import ModelFiles, save_model_info

onnx = pytest.importorskip("onnx")
from onnx import TensorProto, helper, numpy_helper  # noqa: E402

SIZE = 4


def _image_input():
    return helper.make_tensor_value_info("image", TensorProto.FLOAT, ["n", SIZE, SIZE, 3])


def _save(nodes, inputs, path: Path, initializers=()) -> None:
    scores = helper.make_tensor_value_info("scores", TensorProto.FLOAT, ["n", 3])
    graph = helper.make_graph(nodes, "tiny", inputs, [scores], initializer=list(initializers))
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    onnx.checker.check_model(model)
    onnx.save(model, str(path))


def write_tiny_models(folder: Path) -> ModelFiles:
    """Write both tiny models and their info to `folder`."""
    folder.mkdir(parents=True, exist_ok=True)
    files = ModelFiles(folder)
    mean = helper.make_node("ReduceMean", ["image"], ["mean"], axes=[1, 2], keepdims=0)
    _save(
        [mean, helper.make_node("Softmax", ["mean"], ["scores"], axis=1)],
        [_image_input()],
        files.outcome,
    )
    weights = np.zeros((3, 3), np.float32)
    weights[0, 1] = 1000.0
    time = helper.make_tensor_value_info("time", TensorProto.FLOAT, ["n", 3])
    _save(
        [
            mean,
            helper.make_node("MatMul", ["time", "weights"], ["by_time"]),
            helper.make_node("Add", ["mean", "by_time"], ["logits"]),
            helper.make_node("Softmax", ["logits"], ["scores"], axis=1),
        ],
        [_image_input(), time],
        files.guess,
        [numpy_helper.from_array(weights, "weights")],
    )
    save_model_info(files, SIZE)
    return files
