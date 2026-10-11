"""`catpoop watch` (`make dev`): run the live watcher until stopped, one per machine.

With `[alexa_skill] enabled`, the Alexa skill endpoint runs alongside it (docs/alexa-skill.md).
"""

import argparse
import logging
import os
import sys
from collections.abc import Callable, Mapping
from datetime import timedelta
from pathlib import Path
from typing import Any

from catpoop.alexa_skill.run import alexa_skill_running
from catpoop.clock import Clock, SystemClock
from catpoop.config import Config, ConfigError, PartKind, load_config
from catpoop.interfaces import EventLog, OutcomeModel
from catpoop.outcome.model_files import ModelFiles, ModelInfoError
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


def add_command(commands: Any) -> None:
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
    environ: Mapping[str, str] | None = None,
) -> int:
    """Take the watcher lock, make the parts and watch until `stop()` is true.

    `environ` (default: the process's) gives the Alexa skill ID.
    """
    clock = clock or SystemClock()
    try:
        with WatcherLock(config.paths.lock_file or default_lock_path()):
            event_log = registry.create(
                EVENT_LOG, config.parts.event_log, config, config.part_options("event_log")
            )
            env = os.environ if environ is None else environ
            with alexa_skill_running(config, event_log, clock, env):
                _watcher(config, registry, clock, event_log).run(stop)
    except (WatcherAlreadyRunning, UnsafeLockPath) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


def _watcher(config: Config, registry: Registry, clock: Clock, event_log: EventLog) -> Watcher:
    def make[T](slot: Slot[T], kind: PartKind) -> T:
        return registry.create(slot, getattr(config.parts, kind), config, config.part_options(kind))

    store = config.paths.private_data_store
    return Watcher(
        camera=make(CAMERA, "camera"),
        detector=make(DETECTOR, "detector"),
        rules=make(EVENT_RULES, "event_rules"),
        event_log=event_log,
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
        from catpoop.outcome.onnx_outcome import load_outcome_model

        return load_outcome_model(files, config.outcome.runtime)
    except ModelInfoError as error:
        log.warning("no Outcome model, so no Outcome Guess or Outcome: %s", error)
        return None
