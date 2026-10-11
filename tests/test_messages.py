from datetime import UTC, datetime

import pytest

from catpoop.communications.messages import message_text
from catpoop.config import Household
from catpoop.domain import Event, Urgency

AT = datetime(2026, 6, 1, 20, 0, tzinfo=UTC)
HOUSEHOLD = Household(cat="Cat", dog="Dog")


def test_text_comes_from_the_template_for_the_event_kind_with_names_and_details():
    templates = {"visit_started": "{cat} is in the box, maybe {guess}."}
    event = Event("visit_started", Urgency.INFO, AT, {"guess": "poop"})
    assert message_text(templates, HOUSEHOLD, event) == "Cat is in the box, maybe poop."


def test_no_template_means_nothing_to_say():
    assert message_text({}, HOUSEHOLD, Event("poop", Urgency.NORMAL, AT)) is None


def test_a_template_naming_a_missing_detail_says_nothing_and_logs_why(caplog):
    templates = {"poop": "Poop number {number}."}
    assert message_text(templates, HOUSEHOLD, Event("poop", Urgency.NORMAL, AT)) is None
    assert "number" in caplog.text


@pytest.mark.parametrize(
    "template", ["{cat.name} left poop.", "{cat[9]} left poop.", "{cat[x]} left poop."]
)
def test_a_template_reaching_into_something_it_cannot_says_nothing(template):
    event = Event("poop", Urgency.NORMAL, AT)
    assert message_text({"poop": template}, HOUSEHOLD, event) is None
