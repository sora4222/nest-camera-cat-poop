from datetime import timedelta

import pytest

from catpoop.alexa_skill.durations import parse_alexa_duration


@pytest.mark.parametrize(
    ("text", "span"),
    [
        ("PT2H", timedelta(hours=2)),
        ("PT30M", timedelta(minutes=30)),
        ("PT1H30M", timedelta(hours=1, minutes=30)),
        ("PT90S", timedelta(seconds=90)),
        ("P1D", timedelta(days=1)),
        ("P1DT2H", timedelta(days=1, hours=2)),
        ("P1W", timedelta(weeks=1)),
        ("PT1.5H", timedelta(hours=1, minutes=30)),
        ("P3.5W", timedelta(weeks=3.5)),
        ("pt2h", timedelta(hours=2)),
    ],
)
def test_amazon_durations_are_read(text, span):
    assert parse_alexa_duration(text) == span


@pytest.mark.parametrize("text", ["", "P", "PT", "2 hours", "P1M", "P1Y", "PT0M", "PT.5H", "?"])
def test_other_text_is_not_a_duration(text):
    with pytest.raises(ValueError):
        parse_alexa_duration(text)
