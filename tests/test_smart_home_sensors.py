from catpoop.alexa_smart_home.sensors import Sensor, kind_of, sensors
from catpoop.config import Household

TEMPLATES = {
    "visit_started": "{cat} is in the litter box.",
    "poop": "{cat} left poop, a {guess} one.",
    "dog_at_poop": "{dog} is at the poop!",
}
HOUSE = Household(cat="Whiskers", dog="Rex")


def test_one_sensor_per_message_kind():
    assert sensors(TEMPLATES)[2] == Sensor(
        "dog_at_poop", "catpoop-dog-at-poop", "Litter box dog at poop"
    )
    assert len(sensors(TEMPLATES)) == 3


def test_text_is_matched_back_to_its_kind():
    assert kind_of("Whiskers is in the litter box.", TEMPLATES, HOUSE) == "visit_started"
    assert kind_of("Whiskers left poop, a big one.", TEMPLATES, HOUSE) == "poop"
    assert kind_of("Rex is at the poop!", TEMPLATES, HOUSE) == "dog_at_poop"


def test_text_from_no_template_has_no_kind():
    assert kind_of("Hello there", TEMPLATES, HOUSE) is None
    assert kind_of("Tom is in the litter box.", TEMPLATES, HOUSE) is None
