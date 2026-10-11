import logging
from datetime import UTC, datetime

import pytest

from catpoop import observations as obs
from catpoop.domain import Detection, Event, Frame, Outcome, OutcomeScores, Urgency
from catpoop.parts.log_event_rules import LogEventRules
from catpoop.registry import EVENT_RULES, default_registry

AT = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
FRAME = Frame(AT, None)


def scores(best: Outcome) -> OutcomeScores:
    return OutcomeScores({o: 1.0 if o is best else 0.0 for o in Outcome})


def test_frames_and_missing_pictures_make_no_events():
    rules = LogEventRules()
    assert rules.update(obs.Seen(AT, FRAME, (Detection("cat", 0.9, (0, 0, 1, 1)),))) == []
    assert rules.update(obs.NoPicture(AT)) == []


def test_visit_start_passes_the_outcome_guess_through():
    event = LogEventRules().update(obs.VisitStarted(AT, (FRAME,), scores(Outcome.PEE)))
    assert event == [Event("visit_started", Urgency.INFO, AT, {"guess": "pee"})]


def test_visit_end_passes_the_outcome_and_saved_visit_through():
    ended = obs.VisitEnded(AT, AT, (FRAME,), scores(Outcome.POOP), "abc-0000000")
    assert LogEventRules().update(ended) == [
        Event("visit_ended", Urgency.INFO, AT, {"outcome": "poop", "visit": "abc-0000000"})
    ]


def test_visit_without_an_outcome_model_has_no_scores():
    event = LogEventRules().update(obs.VisitStarted(AT, (FRAME,), None))
    assert event == [Event("visit_started", Urgency.INFO, AT, {})]


@pytest.mark.parametrize(
    ("observation", "kind"),
    [(obs.CameraOffline(AT, AT), "camera_offline"), (obs.LoginExpired(AT), "login_expired")],
)
def test_camera_problems_become_events(observation, kind, caplog):
    with caplog.at_level(logging.INFO):
        [event] = LogEventRules().update(observation)
    assert (event.kind, event.urgency) == (kind, Urgency.NORMAL)
    assert kind in caplog.text


def test_log_event_rules_are_registered():
    assert "log" in default_registry().names(EVENT_RULES)
