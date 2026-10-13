"""`catpoop import-history <importer> [paths]`: bring past clips into the Private Data Store."""

import argparse
import logging
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Any

from catpoop.config import ConfigError, load_config
from catpoop.history.clip_store import HistoryClipStore
from catpoop.history.portability_api import PortabilityError
from catpoop.history.run import import_history
from catpoop.registry import HISTORY_IMPORTER, default_registry

IMPORTERS = ["takeout", "portability", "folder"]
"""In the order to try them (see ADR 0001)."""


def add_command(commands: Any) -> None:
    """Add the `import-history` command to the CLI's subparsers."""
    command = commands.add_parser(
        "import-history", help="copy past camera clips into the Private Data Store"
    )
    command.add_argument("importer", choices=IMPORTERS)
    command.add_argument(
        "paths", nargs="*", type=Path, help="archives or folders (default: [history.<importer>])"
    )
    command.add_argument("--job-id", help="portability: resume this export job")
    command.add_argument("--config", type=Path, help="config file (default: $CATPOOP_CONFIG)")


def run(args: argparse.Namespace) -> int:
    """Run `import-history` and return the exit code."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        config = load_config(args.config)
        options: dict[str, Any] = dict(config.history.get(args.importer, {}))
        if args.paths:
            options["paths"] = [str(path) for path in args.paths]
        if args.job_id:
            options["job_id"] = args.job_id
        importer = default_registry().create(HISTORY_IMPORTER, args.importer, config, options)
        counts = import_history(importer, HistoryClipStore(config.paths.private_data_store))
    except (
        ConfigError,
        PortabilityError,
        ValueError,
        OSError,
        zipfile.BadZipFile,
        tarfile.TarError,
    ) as error:
        print(error, file=sys.stderr)
        return 1
    print(f"{args.importer}: {counts.new} new, {counts.known} already stored")
    return 0
