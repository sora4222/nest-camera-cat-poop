"""`catpoop dnd` and `catpoop pee-announcements`: flip the switches the watcher reads.

`make dnd FOR=2h`, `make dnd-off`, `make pee-on` and `make pee-off` call these. They need no
config; they write `switches.json` in the state folder, which a running watcher reads.
"""

import argparse
import re
import sys
from datetime import timedelta
from typing import Any

from catpoop.clock import Clock, SystemClock
from catpoop.communications.switches import Switches
from catpoop.domain import Urgency

COMMANDS = ("dnd", "pee-announcements")
_PART = re.compile(r"(\d+)([dhms])")
_UNITS = {"d": "days", "h": "hours", "m": "minutes", "s": "seconds"}


def parse_duration(text: str) -> timedelta:
    """`2h`, `30m`, `1h30m`, `90s` or `1d` as a time span; ValueError if not like that."""
    text = text.strip().lower()
    parts = _PART.findall(text)
    if not parts or "".join(n + u for n, u in parts) != text:
        raise ValueError(f"not a duration: {text!r} (use e.g. 2h, 30m, 1h30m)")
    span = sum((timedelta(**{_UNITS[u]: int(n)}) for n, u in parts), timedelta())
    if span <= timedelta():
        raise ValueError(f"duration must be more than zero: {text!r}")
    return span


def add_commands(commands: Any) -> None:
    """Add `dnd` and `pee-announcements` to the CLI's subparsers."""
    dnd = commands.add_parser("dnd", help="Do Not Disturb: on for a while, off, or show it")
    group = dnd.add_mutually_exclusive_group()
    group.add_argument("--for", dest="duration", help="how long, e.g. 2h, 30m, 1h30m")
    group.add_argument("--off", action="store_true", help="turn Do Not Disturb off")
    dnd.add_argument(
        "--allow",
        nargs="+",
        choices=[*Urgency, "none"],
        help="Urgencies still spoken (default: [communications] dnd_allow)",
    )
    pee = commands.add_parser("pee-announcements", help="turn Pee announcements on or off")
    pee.add_argument("state", choices=["on", "off"])


def run(args: argparse.Namespace) -> int:
    """Run `dnd` or `pee-announcements` on the switches in the state folder."""
    switches = Switches.default()
    if args.command == "dnd":
        return run_dnd(switches, SystemClock(), args.duration, args.off, args.allow)
    return run_pee(switches, args.state)


def run_dnd(
    switches: Switches,
    clock: Clock,
    duration: str | None = None,
    off: bool = False,
    allow: list[str] | None = None,
) -> int:
    """Turn Do Not Disturb on for `duration`, off, or (with neither) say whether it is on."""
    if off:
        switches.clear_do_not_disturb()
        print("Do Not Disturb is off.")
        return 0
    if duration:
        try:
            span = parse_duration(duration)
        except ValueError as error:
            print(error, file=sys.stderr)
            return 2
        urgencies = None if allow is None else [Urgency(a) for a in allow if a != "none"]
        switches.set_do_not_disturb(clock.now() + span, urgencies)
    dnd = switches.do_not_disturb(clock.now())
    if dnd is None:
        print("Do Not Disturb is off.")
    else:
        through = (
            "[communications] dnd_allow" if dnd.allow is None else ", ".join(dnd.allow) or "none"
        )
        until = dnd.until.astimezone().strftime("%Y-%m-%d %H:%M %Z")
        print(f"Do Not Disturb until {until}; still spoken: {through}.")
    return 0


def run_pee(switches: Switches, state: str) -> int:
    """Turn Pee announcements `on` or `off`."""
    switches.set_pee_announcements(state == "on")
    print(f"Pee announcements are {state}.")
    return 0
