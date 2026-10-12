"""Fail when a pull request changes more than 500 lines of code.

Docs, notebooks, lock files and other non-code files are not counted.
Usage: `uv run --no-project scripts/pr_size.py <base-ref>`.
"""

import subprocess
import sys
from pathlib import PurePosixPath

LIMIT = 500
CODE_SUFFIXES = {".py", ".pyi", ".sh", ".toml", ".yml", ".yaml", ".cfg", ".ini"}
CODE_NAMES = {"Makefile", "Dockerfile"}
SKIP_NAMES = {"uv.lock"}


def is_code(path: str) -> bool:
    """Say if a changed file counts towards the limit."""
    p = PurePosixPath(path)
    if p.name in SKIP_NAMES:
        return False
    return p.name in CODE_NAMES or p.suffix in CODE_SUFFIXES


def changed_lines(base: str) -> dict[str, int]:
    """Lines added plus removed per code file between `base` and HEAD."""
    out = subprocess.run(
        ["git", "diff", "--numstat", "--no-renames", f"{base}...HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    counts: dict[str, int] = {}
    for line in out.splitlines():
        added, removed, path = line.split("\t", 2)
        if added != "-" and is_code(path):
            counts[path] = int(added) + int(removed)
    return counts


def main() -> int:
    """Print changed lines per code file and fail if over the limit."""
    counts = changed_lines(sys.argv[1])
    for path, n in sorted(counts.items()):
        print(f"{n:5} {path}")
    total = sum(counts.values())
    print(f"{total:5} total (limit {LIMIT})")
    if total > LIMIT:
        print("Too big: split this pull request.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
