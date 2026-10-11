"""Command line entry point: `catpoop <command>`. Make targets call these."""

import argparse
import sys
from pathlib import Path

from catpoop.config import ConfigError, load_config
from catpoop.history import command as history_command
from catpoop.outcome import command as outcome_command
from catpoop.registry import (
    CAMERA,
    COMMUNICATIONS,
    DETECTOR,
    EVENT_LOG,
    EVENT_RULES,
    PRESENCE,
    SPEAKER,
    default_registry,
)
from catpoop.visits import command as visits_command


def _check_config(path: Path | None) -> int:
    """Load the config and show which chosen parts are available."""
    try:
        config = load_config(path)
    except ConfigError as error:
        print(error, file=sys.stderr)
        return 1
    registry = default_registry()
    chosen = [
        (CAMERA, config.parts.camera),
        (DETECTOR, config.parts.detector),
        (EVENT_RULES, config.parts.event_rules),
        (EVENT_LOG, config.parts.event_log),
        (PRESENCE, config.parts.presence),
        (COMMUNICATIONS, config.parts.communications),
        *((SPEAKER, speaker.kind) for speaker in config.speakers),
    ]
    print("Config is valid.")
    for slot, name in chosen:
        state = "available" if name in registry.names(slot) else "not available yet"
        print(f"  {slot.kind}: {name} ({state})")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run a command and return its exit code."""
    parser = argparse.ArgumentParser(prog="catpoop")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check-config", help="load the private config and check it")
    check.add_argument("--config", type=Path, help="config file (default: $CATPOOP_CONFIG)")
    history_command.add_command(commands)
    visits_command.add_commands(commands)
    outcome_command.add_commands(commands)
    args = parser.parse_args(argv)
    if args.command == "check-config":
        return _check_config(args.config)
    if args.command == "import-history":
        return history_command.run(args)
    if args.command in visits_command.COMMANDS:
        return visits_command.run(args)
    if args.command in outcome_command.COMMANDS:
        return outcome_command.run(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
