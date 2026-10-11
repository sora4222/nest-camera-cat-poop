from datetime import time
from pathlib import Path

import pytest

from catpoop.config import ConfigError, load_config
from catpoop.domain import Urgency

REPO = Path(__file__).resolve().parent.parent

MINIMAL = """
[parts]
camera = "fake"
detector = "fake"
event_rules = "fake"
event_log = "memory"
presence = "off"
communications = "fake"

[paths]
private_data_store = "/data/store"
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(text)
    return path


def test_example_config_loads():
    config = load_config(REPO / "config.example.toml")
    assert config.parts.presence
    assert config.speakers
    assert config.quiet_hours


def test_minimal_config_gets_defaults(tmp_path):
    config = load_config(write(tmp_path, MINIMAL))
    assert config.paths.private_data_store == Path("/data/store")
    assert config.paths.lock_file is None
    assert config.timers.camera_offline_minutes == 10
    assert config.timers.poop_reminder_max_count == 6
    assert config.speakers == []


def test_quiet_hours_are_parsed(tmp_path):
    text = (
        MINIMAL
        + """
[[quiet_hours]]
days = ["mon", "tue"]
start = "22:00"
end = "07:00"
allow = ["urgent"]
"""
    )
    (quiet,) = load_config(write(tmp_path, text)).quiet_hours
    assert quiet.start == time(22, 0)
    assert quiet.end == time(7, 0)
    assert quiet.allow == [Urgency.URGENT]


def test_part_options_come_from_their_own_table(tmp_path):
    text = MINIMAL + '\n[camera]\ndevice = "litter"\n'
    config = load_config(write(tmp_path, text))
    assert config.part_options("camera") == {"device": "litter"}
    assert config.part_options("detector") == {}


def test_unknown_key_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="tymers"):
        load_config(write(tmp_path, MINIMAL + "\n[tymers]\n"))


def test_missing_part_choice_is_an_error(tmp_path):
    text = MINIMAL.replace('camera = "fake"\n', "")
    with pytest.raises(ConfigError, match="camera"):
        load_config(write(tmp_path, text))


def test_missing_file_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="make setup"):
        load_config(tmp_path / "config.toml")


def test_path_comes_from_environment(tmp_path, monkeypatch):
    path = write(tmp_path, MINIMAL)
    monkeypatch.setenv("CATPOOP_CONFIG", str(path))
    assert load_config().paths.private_data_store == Path("/data/store")


def test_visit_settings_have_defaults(tmp_path):
    visits = load_config(write(tmp_path, MINIMAL)).visits
    assert visits.max_store_gb == 500
    assert visits.cat_label == "cat"
    assert visits.litter_box == (0.0, 0.0, 1.0, 1.0)


def test_visit_settings_are_read(tmp_path):
    text = MINIMAL + "[visits]\nmax_store_gb = 2\nlitter_box = [0.1, 0.2, 0.9, 1.0]\n"
    visits = load_config(write(tmp_path, text)).visits
    assert visits.max_store_gb == 2
    assert visits.litter_box == (0.1, 0.2, 0.9, 1.0)


def test_outcome_settings_have_defaults(tmp_path):
    outcome = load_config(write(tmp_path, MINIMAL)).outcome
    assert outcome.models == Path("models/outcome")
    assert outcome.runtime == "auto"
    assert outcome.backbone == "mobilenet"
    assert 0 < outcome.validation_fraction < 1
    assert outcome.timezone == "UTC"


def test_outcome_settings_are_read_and_checked(tmp_path):
    text = MINIMAL + '[outcome]\nimage_size = 64\nbackbone = "small"\n'
    outcome = load_config(write(tmp_path, text)).outcome
    assert outcome.image_size == 64
    assert outcome.backbone == "small"
    with pytest.raises(ConfigError, match=r"outcome\.backbone"):
        load_config(write(tmp_path, MINIMAL + '[outcome]\nbackbone = "huge"\n'))
    with pytest.raises(ConfigError, match=r"outcome\.runtime"):
        load_config(write(tmp_path, MINIMAL + '[outcome]\nruntime = "tpu"\n'))


def test_outcome_timezone_must_be_a_known_zone(tmp_path):
    text = MINIMAL + '[outcome]\ntimezone = "Australia/Melbourne"\n'
    assert load_config(write(tmp_path, text)).outcome.timezone == "Australia/Melbourne"
    with pytest.raises(ConfigError, match=r"outcome\.timezone"):
        load_config(write(tmp_path, MINIMAL + '[outcome]\ntimezone = "Mars/Olympus"\n'))
