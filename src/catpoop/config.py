"""Load and check the private config file (`config.toml`, never committed).

The path is `$CATPOOP_CONFIG` if set, else `config.toml` in the current folder.
See `config.example.toml` for every setting.
"""

import os
import tomllib
from datetime import time
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from catpoop.domain import Urgency

PartKind = Literal["camera", "detector", "event_rules", "event_log", "presence", "communications"]
Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class ConfigError(Exception):
    """The config file is missing or has a wrong value."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Open(BaseModel):
    """A table that also holds plug-in specific keys."""

    model_config = ConfigDict(extra="allow", frozen=True)


class PartChoices(_Strict):
    """Which implementation to use for each swappable part, by registered name."""

    camera: str
    detector: str
    event_rules: str
    event_log: str
    presence: str
    communications: str


class Paths(_Strict):
    """Where things live outside the repo."""

    private_data_store: Path
    lock_file: Path | None = None  # None: `watcher_lock.default_lock_path()`


class Household(_Strict):
    """Names used in Message templates. Real names only ever live in the private config."""

    cat: str = "the cat"
    dog: str = "the dog"


class ListenerSettings(_Open):
    """A person who may hear Announcements. Presence options are plug-in specific."""

    name: str


class SpeakerSettings(_Open):
    """A device that can say a message. `kind` picks the speaker plug-in."""

    name: str
    kind: str


class QuietHours(_Strict):
    """A repeating quiet time. `allow` lists the Urgencies that may still be spoken."""

    days: list[Weekday]
    start: time
    end: time
    allow: list[Urgency] = []


class Timers(_Strict):
    """Times and limits for the event rules."""

    camera_offline_minutes: int = 10
    poop_reminder_first_minutes: int = 1
    poop_reminder_max_minutes: int = 60
    poop_reminder_max_count: int = 6
    login_expired_reminder_at: time = time(18, 0)


class VisitSettings(_Strict):
    """How clips are cut into Visits, and how much the Private Data Store may hold."""

    frame_seconds: float = 0.5
    """Time between the frames that are checked and kept."""
    cat_label: str = "cat"
    """The detector label of the Cat."""
    litter_box: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    """Left, top, right, bottom of the Litter Box as fractions of the picture."""
    end_gap_seconds: float = 3.0
    """The Cat must be gone this long for a Visit to end."""
    min_seconds: float = 2.0
    """Shorter Visits are dropped."""
    padding_seconds: float = 1.0
    """Kept before and after each Visit."""
    max_store_gb: float = 500
    """Above this, the oldest clips with no labeled Visit are deleted."""


class WatcherSettings(_Strict):
    """How often the live watcher checks the camera (`make dev`)."""

    check_seconds: float = Field(0.25, gt=0)
    """Time between detector runs on the newest picture."""


class OutcomeSettings(_Strict):
    """Where the Outcome model lives and how `make train` trains it."""

    models: Path = Path("models/outcome")
    """Folder of the exported models; a relative path is inside the Private Data Store."""
    runtime: Literal["auto", "cpu", "amd", "nvidia"] = "auto"
    """ONNX Runtime providers to run the models on (see onnx_session)."""
    backbone: Literal["mobilenet", "small"] = "mobilenet"
    """`mobilenet`: MobileNetV3 Small pretrained on ImageNet (downloaded once); `small`: a
    tiny network learned from scratch."""
    image_size: int = Field(128, ge=32)
    """Pictures are resized to this many pixels square."""
    epochs: int = Field(20, ge=1)
    batch_size: int = Field(16, ge=1)
    validation_fraction: float = Field(0.2, ge=0, lt=1)
    """Share of Visits held out to measure accuracy."""
    guess_frames_per_visit: int = Field(5, ge=1)
    """Frames from the middle of each Visit used to learn the Outcome Guess."""
    timezone: str = "UTC"
    """IANA time zone of the Litter Box, e.g. `Australia/Melbourne`; the time of day is
    read in it. Saved with the models, so the server uses the zone they were trained in."""

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, name: str) -> str:
        try:
            ZoneInfo(name)
        except (ValueError, KeyError, OSError):  # ZoneInfoNotFoundError is a KeyError
            raise ValueError(f"unknown time zone {name!r}") from None
        return name


class Config(_Strict):
    """The whole private config."""

    parts: PartChoices
    paths: Paths
    household: Household = Household()
    listeners: list[ListenerSettings] = []
    speakers: list[SpeakerSettings] = []
    messages: dict[str, str] = {}
    quiet_hours: list[QuietHours] = []
    timers: Timers = Timers()
    visits: VisitSettings = VisitSettings()
    outcome: OutcomeSettings = OutcomeSettings()
    watcher: WatcherSettings = WatcherSettings()
    # Options for the chosen implementation of each part.
    camera: dict[str, Any] = {}
    detector: dict[str, Any] = {}
    event_rules: dict[str, Any] = {}
    event_log: dict[str, Any] = {}
    presence: dict[str, Any] = {}
    communications: dict[str, Any] = {}
    # Options for each history importer, one `[history.<name>]` table each.
    history: dict[str, dict[str, Any]] = {}

    def part_options(self, kind: PartKind) -> dict[str, Any]:
        """The `[<kind>]` table: options for the chosen implementation of that part."""
        return getattr(self, kind)


def config_path() -> Path:
    """The config file to use: `$CATPOOP_CONFIG`, else `./config.toml`."""
    return Path(os.environ.get("CATPOOP_CONFIG", "config.toml"))


def load_config(path: Path | None = None) -> Config:
    """Read and check the config file, raising `ConfigError` with a readable reason."""
    path = path or config_path()
    try:
        data = tomllib.loads(path.read_text())
    except FileNotFoundError:
        raise ConfigError(
            f"{path} not found; copy config.example.toml to it (`make setup`)"
        ) from None
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path}: {error}") from None
    try:
        return Config.model_validate(data)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in e['loc'])}: {e['msg']}" for e in error.errors()
        )
        raise ConfigError(f"{path}: {problems}") from None
