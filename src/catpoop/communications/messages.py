"""Spoken text from the Message templates in the private config (`[messages]`)."""

import logging
from collections.abc import Mapping

from catpoop.config import Household
from catpoop.domain import Event

log = logging.getLogger(__name__)


def message_text(templates: Mapping[str, str], household: Household, event: Event) -> str | None:
    """The template for `event.kind` filled with `{cat}`, `{dog}` and the Event's details.

    None when there is no template, or it names something the Event does not have.
    """
    template = templates.get(event.kind)
    if template is None:
        return None
    try:
        return template.format(**{"cat": household.cat, "dog": household.dog, **event.details})
    except (KeyError, IndexError, AttributeError, TypeError, ValueError) as error:
        log.warning("message %r cannot be filled in: %r", event.kind, error)
        return None
