"""Export a trained Keras Outcome network to ONNX with tf2onnx (train extra).

The ONNX file has the inputs and output `model_files` describes: `image` (and `time`
for the Outcome Guess) in, `scores` out.
"""

from pathlib import Path

import keras
import tensorflow as tf
import tf2onnx

from catpoop.outcome.features import TIME_FEATURES

OPSET = 17


def export_onnx(model: keras.Model, path: Path, image_size: int, with_time: bool) -> None:
    """Write `model` in inference mode (no augmentation or dropout) to `path`."""
    signature = [tf.TensorSpec([None, image_size, image_size, 3], tf.float32, name="image")]
    if with_time:
        signature.append(tf.TensorSpec([None, TIME_FEATURES], tf.float32, name="time"))

    @tf.function(input_signature=signature)
    def scores(*inputs: tf.Tensor) -> dict[str, tf.Tensor]:
        return {"scores": model(list(inputs), training=False)}

    path.parent.mkdir(parents=True, exist_ok=True)
    tf2onnx.convert.from_function(
        scores, input_signature=signature, opset=OPSET, output_path=str(path)
    )
