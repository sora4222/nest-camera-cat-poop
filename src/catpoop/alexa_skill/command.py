"""`catpoop alexa-tunnel` (`make alexa-tunnel`): print the tunnel setup for `[alexa_skill]`."""

import argparse
import sys
from pathlib import Path
from typing import Any

from catpoop.alexa_skill.tunnel import tunnel_setup
from catpoop.config import ConfigError, load_config


def add_command(commands: Any) -> None:
    """Add `alexa-tunnel` to the CLI's subparsers."""
    tunnel = commands.add_parser(
        "alexa-tunnel", help="show how to open only /alexa with the configured tunnel"
    )
    tunnel.add_argument("--config", type=Path, help="config file (default: $CATPOOP_CONFIG)")


def run(args: argparse.Namespace) -> int:
    """Print the setup for the tunnel chosen in the config."""
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(error, file=sys.stderr)
        return 1
    print(tunnel_setup(config.alexa_skill), end="")
    return 0
