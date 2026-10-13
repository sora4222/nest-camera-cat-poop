"""The Outcome model on the server: the exported ONNX files run with ONNX Runtime, no TensorFlow."""

from typing import Any

import numpy as np

from catpoop.domain import Frame, OutcomeScores
from catpoop.onnx_session import open_session
from catpoop.outcome.features import prepare_image, time_features
from catpoop.outcome.model_files import ModelFiles, ModelInfo, ModelInfoError, load_model_info


class OnnxOutcomeModel:
    """An `OutcomeModel` from two ONNX Runtime sessions (or fakes with `run`)."""

    def __init__(self, outcome: Any, guess: Any, info: ModelInfo) -> None:
        """The Outcome Guess reads the time of day in `info.zone`, the zone it was trained in."""
        self._outcome = outcome
        self._guess = guess
        self._info = info

    @property
    def info(self) -> ModelInfo:
        """What the models take and give, and how they were trained."""
        return self._info

    def outcome(self, surface: Frame) -> OutcomeScores:
        """The Outcome, from a Frame of the litter surface after the Cat has left."""
        return self._scores(self._outcome.run(["scores"], {"image": self._image(surface)}))

    def guess(self, stance: Frame) -> OutcomeScores:
        """The Outcome Guess, from a Frame of the Cat in the Litter Box and its time of day."""
        time = time_features(stance.taken_at, self._info.zone)[None]
        feed = {"image": self._image(stance), "time": time}
        return self._scores(self._guess.run(["scores"], feed))

    def _image(self, frame: Frame) -> np.ndarray:
        return prepare_image(frame.image, self._info.image_size)[None]

    def _scores(self, results: list[np.ndarray]) -> OutcomeScores:
        row = results[0][0].tolist()
        return OutcomeScores(dict(zip(self._info.classes, row, strict=True)))


def load_outcome_model(files: ModelFiles, runtime: str) -> OnnxOutcomeModel:
    """Open the Outcome models in `files` on the providers `runtime` asks for (see onnx_session)."""
    info = load_model_info(files)
    for path in (files.outcome, files.guess):
        if not path.is_file():
            raise ModelInfoError(f"{path} not found; run `make train` first")
    return OnnxOutcomeModel(
        open_session(files.outcome, runtime), open_session(files.guess, runtime), info
    )
