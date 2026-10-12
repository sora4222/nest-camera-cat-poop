"""Read the ISO 8601 durations Alexa's AMAZON.DURATION slot gives, such as `PT2H`."""

import re
from datetime import timedelta

_N = r"\d+(?:\.\d+)?"  # Alexa may give fractions, e.g. P3.5W
_DURATION = re.compile(
    rf"P(?:(?P<weeks>{_N})W)?(?:(?P<days>{_N})D)?"
    rf"(?:T(?:(?P<hours>{_N})H)?(?:(?P<minutes>{_N})M)?(?:(?P<seconds>{_N})S)?)?",
    re.IGNORECASE,
)


def parse_alexa_duration(text: str) -> timedelta:
    """`PT2H`, `PT30M`, `P1D`, `P3.5W`... as a time span; ValueError for months, years or zero."""
    match = _DURATION.fullmatch(text.strip())
    if not match or text.strip().upper().endswith(("P", "T")):
        raise ValueError(f"not a duration Alexa gives: {text!r}")
    span = timedelta(**{unit: float(value) for unit, value in match.groupdict().items() if value})
    if span <= timedelta():
        raise ValueError(f"duration must be more than zero: {text!r}")
    return span
