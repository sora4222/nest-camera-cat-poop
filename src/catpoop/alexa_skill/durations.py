"""Read the ISO 8601 durations Alexa's AMAZON.DURATION slot gives, such as `PT2H`."""

import re
from datetime import timedelta

_DURATION = re.compile(
    r"P(?:(?P<weeks>\d+)W)?(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?",
    re.IGNORECASE,
)


def parse_alexa_duration(text: str) -> timedelta:
    """`PT2H`, `PT30M`, `P1D`... as a time span; ValueError for months, years or zero."""
    match = _DURATION.fullmatch(text.strip())
    if not match or text.strip().upper().endswith(("P", "T")):
        raise ValueError(f"not a duration Alexa gives: {text!r}")
    span = timedelta(**{unit: int(value) for unit, value in match.groupdict().items() if value})
    if span <= timedelta():
        raise ValueError(f"duration must be more than zero: {text!r}")
    return span
