"""The files `make train` writes to the models folder, and `outcome.json` that describes them.

- `outcome.onnx`: input `image` `[N, S, S, 3]` float32 pixels 0-255, output `scores` `[N, 3]`.
- `outcome_guess.onnx`: inputs `image` and `time` `[N, 3]` (see `features.time_features`).
- `outcome.json`: the picture size `S`, the Outcome of each score, the time zone the
  time of day was read in and the share of Visits held out from training.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from catpoop.domain import Outcome
from catpoop.outcome.features import CLASSES


class ModelInfoError(Exception):
    """The Outcome model files are missing or do not fit together."""


@dataclass(frozen=True)
class ModelFiles:
    """Paths of the Outcome model files in one folder."""

    folder: Path

    @classmethod
    def in_store(cls, private_data_store: Path, models: Path) -> "ModelFiles":
        """The files in `models`; a relative path is inside the Private Data Store."""
        return cls(private_data_store / models)

    @property
    def outcome(self) -> Path:
        """The Outcome model (litter surface)."""
        return self.folder / "outcome.onnx"

    @property
    def guess(self) -> Path:
        """The Outcome Guess model (the Cat's stance and the time of day)."""
        return self.folder / "outcome_guess.onnx"

    @property
    def info(self) -> Path:
        """What the models expect and give."""
        return self.folder / "outcome.json"


@dataclass(frozen=True)
class ModelInfo:
    """What the models take and give, and the zone the time of day is read in."""

    image_size: int
    classes: tuple[Outcome, ...]
    zone: ZoneInfo
    validation_fraction: float


def save_model_info(
    files: ModelFiles, image_size: int, timezone: str, validation_fraction: float
) -> None:
    """Write `outcome.json` for models trained on `image_size` pictures in `timezone`."""
    info = {
        "image_size": image_size,
        "classes": [c.value for c in CLASSES],
        "timezone": timezone,
        "validation_fraction": validation_fraction,
    }
    files.info.write_text(json.dumps(info, indent=2) + "\n")


def load_model_info(files: ModelFiles) -> ModelInfo:
    """Read `outcome.json`, raising `ModelInfoError` if it is missing or wrong."""
    try:
        data = json.loads(files.info.read_text())
        classes = tuple(Outcome(name) for name in data["classes"])
        size = int(data["image_size"])
        zone = ZoneInfo(data["timezone"])
        fraction = float(data["validation_fraction"])
    except FileNotFoundError:
        raise ModelInfoError(f"{files.info} not found; run `make train` first") from None
    except (ValueError, KeyError, TypeError) as error:
        raise ModelInfoError(f"{files.info}: {error!r}") from None
    if sorted(classes) != sorted(Outcome):
        raise ModelInfoError(f"{files.info}: classes must be each Outcome once")
    return ModelInfo(size, classes, zone, fraction)
