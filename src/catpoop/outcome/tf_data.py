"""Read training examples with `tf.data` (train extra).

Pictures are loaded with `features.load_image`, the same code the server uses, so a
model sees the same pixels in training and on the server.
"""

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import tensorflow as tf

from catpoop.outcome.examples import Example
from catpoop.outcome.features import CLASSES, TIME_FEATURES, load_image, time_features


def make_dataset(
    examples: Sequence[Example],
    image_size: int,
    batch_size: int,
    with_time: bool,
    shuffle: bool = False,
) -> tf.data.Dataset:
    """Batches of `(inputs, class index)`; inputs are `{"image"}`, plus `{"time"}` if asked."""
    paths = [str(e.picture) for e in examples]
    times = np.array([time_features(e.taken_at) for e in examples], np.float32).reshape(
        -1, TIME_FEATURES
    )
    labels = np.array([CLASSES.index(e.outcome) for e in examples], np.int32)
    data = tf.data.Dataset.from_tensor_slices((paths, times, labels))
    if shuffle:
        data = data.shuffle(len(examples), reshuffle_each_iteration=True)

    def load(path: tf.Tensor, time: tf.Tensor, label: tf.Tensor):
        image = tf.numpy_function(
            lambda p: load_image(Path(p.decode()), image_size), [path], tf.float32
        )
        image.set_shape((image_size, image_size, 3))
        inputs = {"image": image, "time": time} if with_time else {"image": image}
        return inputs, label

    return data.map(load, num_parallel_calls=tf.data.AUTOTUNE).batch(batch_size).prefetch(1)
