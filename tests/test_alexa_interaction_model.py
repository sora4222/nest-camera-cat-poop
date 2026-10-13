"""The interaction model in the repo matches what the skill code answers."""

import json
import re
from pathlib import Path

from catpoop.alexa_skill.skill import INTENTS

MODEL = Path(__file__).parents[1] / "alexa" / "interactionModels" / "custom" / "en-US.json"


def language_model() -> dict:
    return json.loads(MODEL.read_text())["interactionModel"]["languageModel"]


def test_every_intent_in_the_model_has_a_handler_and_back():
    names = {intent["name"] for intent in language_model()["intents"]}
    assert names == set(INTENTS)


def test_invocation_name_is_lower_case_words():
    assert re.fullmatch(r"[a-z]+( [a-z]+)+", language_model()["invocationName"])


def test_samples_are_unique_and_use_only_declared_slots():
    seen: set[str] = set()
    for intent in language_model()["intents"]:
        slots = {slot["name"] for slot in intent.get("slots", [])}
        for sample in intent["samples"]:
            assert sample not in seen, sample
            seen.add(sample)
            assert re.fullmatch(r"[a-z' {}]+", sample), sample
            assert set(re.findall(r"{(\w+)}", sample)) <= slots, sample


def test_quiet_intents_take_an_amazon_duration():
    for name in ("QuietPoopIntent", "QuietVisitsIntent", "DurationIntent"):
        quiet = next(i for i in language_model()["intents"] if i["name"] == name)
        assert quiet["slots"] == [{"name": "duration", "type": "AMAZON.DURATION"}]


def test_a_slot_only_sample_is_alone_in_its_intent():
    for intent in language_model()["intents"]:
        if any(re.fullmatch(r"{\w+}", sample) for sample in intent["samples"]):
            assert len(intent["samples"]) == 1, intent["name"]
