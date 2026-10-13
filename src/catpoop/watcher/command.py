"""`catpoop watch` (`make dev`): run the live watcher until stopped, one per machine."""

import argparse
import logging
import sys
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

from catpoop.clock import Clock, SystemClock
from catpoop.config import Config, ConfigError, PartKind, load_config
from catpoop.interfaces import OutcomeModel
from catpoop.outcome.model_files import ModelFiles, ModelInfoError
from catpoop.outcome.onnx_outcome import load_outcome_model
from catpoop.registry import (
    CAMERA,
    COMMUNICATIONS,
    DETECTOR,
    EVENT_LOG,
    EVENT_RULES,
    Registry,
    Slot,
    default_registry,
)
from catpoop.watcher.recorder import LiveVisitRecorder
from catpoop.watcher.watcher import Watcher
from catpoop.watcher_lock import (
    UnsafeLockPath,
    WatcherAlreadyRunning,
    WatcherLock,
    default_lock_path,
)

log = logging.getLogger(__name__)


def add_command(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    """Add `watch` to the CLI's subparsers."""
    watch = commands.add_parser("watch", help="watch the Litter Box live until stopped")
    watch.add_argument("--config", type=Path, help="config file (default: $CATPOOP_CONFIG)")


def run(args: argparse.Namespace) -> int:
    """Load the config and run the watcher; Ctrl+C stops it."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    try:
        return start_watcher(load_config(args.config), default_registry())
    except ConfigError as error:
        print(error, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


def start_watcher(
    config: Config,
    registry: Registry,
    clock: Clock | None = None,
    stop: Callable[[], bool] = lambda: False,
) -> int:
    """Take the watcher lock, make the parts and watch until `stop()` is true."""
    try:
        with WatcherLock(config.paths.lock_file or default_lock_path()):
            _watcher(config, registry, clock or SystemClock()).run(stop)
    except (WatcherAlreadyRunning, UnsafeLockPath) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


def _watcher(config: Config, registry: Registry, clock: Clock) -> Watcher:
    def make[T](slot: Slot[T], kind: PartKind) -> T:
        return registry.create(slot, getattr(config.parts, kind), config, config.part_options(kind))

    store = config.paths.private_data_store
    return Watcher(
        camera=make(CAMERA, "camera"),
        detector=make(DETECTOR, "detector"),
        rules=make(EVENT_RULES, "event_rules"),
        event_log=make(EVENT_LOG, "event_log"),
        communications=make(COMMUNICATIONS, "communications"),
        recorder=LiveVisitRecorder(store, config.visits),
        clock=clock,
        visits=config.visits,
        offline_after=timedelta(minutes=config.timers.camera_offline_minutes),
        check_seconds=config.watcher.check_seconds,
        outcome_model=_outcome_model(config),
        surface_check_seconds=config.watcher.surface_check_seconds,
    )


def _outcome_model(config: Config) -> OutcomeModel | None:
    """The trained Outcome model, or None (with a warning) if there is none yet."""
    files = ModelFiles.in_store(config.paths.private_data_store, config.outcome.models)
    try:
        return load_outcome_model(files, config.outcome.runtime)
    except ModelInfoError as error:
        log.warning("no Outcome model, so no Outcome Guess or Outcome: %s", error)
        return None
