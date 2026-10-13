"""One virtual motion sensor per message kind, and which sensor a spoken text belongs to."""

import re
import string
from collections.abc import Mapping
from dataclasses import dataclass

from catpoop.config import Household


@dataclass(frozen=True)
class Sensor:
    """A virtual motion sensor shown in the Alexa app; a routine on it says one message."""

    kind: str
    endpoint_id: str
    name: str


def sensors(templates: Mapping[str, str]) -> list[Sensor]:
    """A sensor for each message kind in `[messages]`, e.g. "Litter box poop"."""
    return [
        Sensor(kind, f"catpoop-{kind.replace('_', '-')}", f"Litter box {kind.replace('_', ' ')}")
        for kind in templates
    ]


def kind_of(text: str, templates: Mapping[str, str], household: Household) -> str | None:
    """The message kind whose template could have made `text`, else None."""
    for kind, template in templates.items():
        if re.fullmatch(_pattern(template, household), text):
            return kind
    return None


def _pattern(template: str, household: Household) -> str:
    known = {"cat": household.cat, "dog": household.dog}
    out = []
    for literal, field, _spec, _conversion in string.Formatter().parse(template):
        out.append(re.escape(literal))
        if field is not None:
            out.append(re.escape(known[field]) if field in known else ".*?")
    return "".join(out)
