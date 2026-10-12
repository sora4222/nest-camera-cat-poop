"""The Keras network for the Outcome and the Outcome Guess (train extra).

Input `image` is `[S, S, 3]` float pixels 0-255; the Outcome Guess also takes `time`
(see `features.time_features`). Output `scores` is one softmax score per Outcome in
`features.CLASSES` order.
"""

import keras

from catpoop.outcome.features import CLASSES, TIME_FEATURES

BACKBONES = ("mobilenet", "small")


def build_model(image_size: int, backbone: str, with_time: bool) -> keras.Model:
    """A compiled model; `with_time` adds the time of day input for the Outcome Guess."""
    image = keras.Input((image_size, image_size, 3), name="image")
    augmented = keras.layers.RandomFlip("horizontal")(image)
    features = _backbone(backbone, image_size)(augmented)
    inputs = [image]
    if with_time:
        time = keras.Input((TIME_FEATURES,), name="time")
        inputs.append(time)
        features = keras.layers.Concatenate()([features, keras.layers.Dense(8, "relu")(time)])
    features = keras.layers.Dropout(0.2)(features)
    scores = keras.layers.Dense(len(CLASSES), "softmax", name="scores")(features)
    model = keras.Model(inputs, scores)
    model.compile(
        optimizer=keras.optimizers.Adam(1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def _backbone(name: str, image_size: int) -> keras.Model:
    """Picture features. `mobilenet` is pretrained on ImageNet and kept frozen."""
    if name == "mobilenet":
        base = keras.applications.MobileNetV3Small(
            input_shape=(image_size, image_size, 3),
            include_top=False,
            weights="imagenet",
            pooling="avg",
            include_preprocessing=True,
        )
        base.trainable = False
        return base
    if name == "small":
        return keras.Sequential(
            [
                keras.layers.Rescaling(1 / 255),
                keras.layers.Conv2D(16, 3, activation="relu"),
                keras.layers.MaxPooling2D(),
                keras.layers.Conv2D(32, 3, activation="relu"),
                keras.layers.MaxPooling2D(),
                keras.layers.Conv2D(64, 3, activation="relu"),
                keras.layers.GlobalAveragePooling2D(),
            ],
            name="small",
        )
    raise ValueError(f"unknown backbone {name!r}; use one of {', '.join(BACKBONES)}")
