"""`catpoop watch` (`make dev`): run the live watcher until stopped, one per machine.

Poop the event log says is still in the Litter Box is picked up again at startup.
With `[alexa_skill] enabled`, the Alexa skill endpoint runs alongside it (docs/alexa-skill.md).
"""

import argparse
import logging
import os
import sys
from collections.abc import Callable, Mapping
from datetime import timedelta
from pathlib import Path

from catpoop.alexa_skill.poop_status import litter_box_status
from catpoop.alexa_skill.run import alexa_app, serve_in_background
from catpoop.clock import Clock, SystemClock
from catpoop.config import Config, ConfigError, PartKind, load_config
from catpoop.interfaces import EventLog, OutcomeModel, ResumesPoop
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
            app = alexa_app(config, event_log, clock, env)
            if app is not None:
                serve_in_background(app, config.alexa_skill)
            _watcher(config, registry, clock, event_log).run(stop)
    except (WatcherAlreadyRunning, UnsafeLockPath) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


def _watcher(config: Config, registry: Registry, clock: Clock, event_log: EventLog) -> Watcher:
    def make[T](slot: Slot[T], kind: PartKind) -> T:
        return registry.create(slot, getattr(config.parts, kind), config, config.part_options(kind))

    store = config.paths.private_data_store
    rules = make(EVENT_RULES, "event_rules")
    communications = make(COMMUNICATIONS, "communications")
    _resume_poop(event_log, clock, [rules, communications])
    return Watcher(
        camera=make(CAMERA, "camera"),
        detector=make(DETECTOR, "detector"),
        rules=rules,
        event_log=event_log,
        communications=communications,
        recorder=LiveVisitRecorder(store, config.visits),
        clock=clock,
        visits=config.visits,
        offline_after=timedelta(minutes=config.timers.camera_offline_minutes),
        check_seconds=config.watcher.check_seconds,
        outcome_model=_outcome_model(config),
        surface_check_seconds=config.watcher.surface_check_seconds,
    )


def _resume_poop(event_log: EventLog, clock: Clock, parts: list[object]) -> None:
    """Tell the parts about Poop the event log says is still in the Litter Box (a restart)."""
    newest = litter_box_status(event_log).newest_poop
    if newest is None:
        return
    log.info("Poop found at %s is still in the Litter Box", newest.isoformat())
    for part in parts:
        if isinstance(part, ResumesPoop):
            part.resume_poop(newest, clock.now())


def _outcome_model(config: Config) -> OutcomeModel | None:
    """The trained Outcome model, or None (with a warning) if there is none yet."""
    files = ModelFiles.in_store(config.paths.private_data_store, config.outcome.models)
    try:
        return load_outcome_model(files, config.outcome.runtime)
    except ModelInfoError as error:
        log.warning("no Outcome model, so no Outcome Guess or Outcome: %s", error)
        return None
