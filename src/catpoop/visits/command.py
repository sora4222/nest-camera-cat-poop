"""`catpoop cut-visits`, `catpoop label` and `catpoop add-visit`."""

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from catpoop.config import Config, ConfigError, load_config
from catpoop.domain import Outcome
from catpoop.registry import DETECTOR, default_registry
from catpoop.visits.add_visit import add_visit
from catpoop.visits.cut import cut_clips
from catpoop.visits.labeling_app import LabelingApp
from catpoop.visits.labeling_server import make_server
from catpoop.visits.retention import prune_clips
from catpoop.visits.store import VisitStore
from catpoop.visits.video import VideoError

COMMANDS = ["cut-visits", "label", "add-visit"]


def add_commands(commands: Any) -> None:
    """Add the Visit commands to the CLI's subparsers."""
    cut = commands.add_parser(
        "cut-visits", help="cut new history clips into Visits, then keep the store under its limit"
    )
    label = commands.add_parser("label", help="open the labeling page on this machine")
    label.add_argument("--port", type=int, default=8765)
    add = commands.add_parser("add-visit", help="add whole clips found by hand to the dataset")
    add.add_argument("outcome", choices=[o.value for o in Outcome])
    add.add_argument("clips", nargs="+", type=Path)
    for command in (cut, label, add):
        command.add_argument("--config", type=Path, help="config file (default: $CATPOOP_CONFIG)")


def run(args: argparse.Namespace) -> int:
    """Run one of the Visit commands and return the exit code."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        config = load_config(args.config)
        if args.command == "cut-visits":
            return _cut(config)
        if args.command == "label":
            return _label(config, args.port)
        return _add(config, Outcome(args.outcome), args.clips)
    except (ConfigError, OSError) as error:
        print(error, file=sys.stderr)
        return 1


def _cut(config: Config) -> int:
    store = config.paths.private_data_store
    detector = default_registry().create(
        DETECTOR, config.parts.detector, config, config.part_options("detector")
    )
    counts = cut_clips(store, detector, config.visits)
    print(f"{counts.clips} clips cut, {counts.visits} Visits found, {counts.failed} unreadable")
    removed = prune_clips(store, int(config.visits.max_store_gb * 1e9))
    if removed:
        print(f"{len(removed)} unlabeled clips deleted to stay under the size limit")
    return 0


def _label(config: Config, port: int) -> int:
    server = make_server(LabelingApp(VisitStore(config.paths.private_data_store)), port)
    print(f"Labeling page: http://localhost:{server.server_address[1]}/ (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _add(config: Config, outcome: Outcome, clips: list[Path]) -> int:
    failed = 0
    now = datetime.now(UTC)
    for clip in clips:
        try:
            visit = add_visit(clip, outcome, config.paths.private_data_store, config.visits, now)
        except VideoError as error:
            print(error, file=sys.stderr)
            failed += 1
            continue
        print(f"{clip.name} -> {outcome.value}/{visit.id} ({visit.frames} frames)")
    return 1 if failed else 0
