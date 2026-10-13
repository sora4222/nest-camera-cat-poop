import numpy as np
import pytest
from fake_video import write_clip

from catpoop.cli import main
from catpoop.domain import Detection
from catpoop.registry import DETECTOR, Registry
from catpoop.visits import command
from catpoop.visits.store import VisitStore


def write_config(tmp_path, extra=""):
    path = tmp_path / "config.toml"
    path.write_text(
        f"""
[parts]
camera = "fake"
detector = "bright"
event_rules = "fake"
event_log = "memory"
presence = "off"
communications = "fake"

[paths]
private_data_store = "{tmp_path / "store"}"

[visits]
frame_seconds = 0.5
min_seconds = 1
{extra}
"""
    )
    return path


class BrightIsCat:
    def detect(self, frame):
        if np.asarray(frame.image).mean() > 128:
            return [Detection("cat", 0.9, (0.4, 0.4, 0.6, 0.6))]
        return []


@pytest.fixture
def registry(monkeypatch):
    registry = Registry()
    registry.add(DETECTOR, "bright", lambda config, options: BrightIsCat())
    monkeypatch.setattr(command, "default_registry", lambda: registry)
    return registry


def test_cut_visits_cuts_new_clips(tmp_path, registry, capsys):
    clips = tmp_path / "store" / "history" / "clips"
    clips.mkdir(parents=True)
    write_clip(clips / f"{'a' * 64}.mp4", [20] * 8 + [230] * 8 + [20] * 8)
    assert main(["cut-visits", "--config", str(write_config(tmp_path))]) == 0
    assert "1 clips cut, 1 Visits found" in capsys.readouterr().out
    assert len(VisitStore(tmp_path / "store").unlabeled()) == 1


def test_cut_visits_prunes_the_store(tmp_path, registry, capsys):
    clips = tmp_path / "store" / "history" / "clips"
    clips.mkdir(parents=True)
    write_clip(clips / f"{'a' * 64}.mp4", [20] * 8)
    config = write_config(tmp_path, "max_store_gb = 0")
    assert main(["cut-visits", "--config", str(config)]) == 0
    assert "1 unlabeled clips deleted" in capsys.readouterr().out
    assert list(clips.glob("*.mp4")) == []


def test_cut_visits_reports_a_missing_detector(tmp_path, capsys):
    config = write_config(tmp_path).read_text().replace('"bright"', '"nope"')
    (tmp_path / "config.toml").write_text(config)
    assert main(["cut-visits", "--config", str(tmp_path / "config.toml")]) == 1
    assert "nope" in capsys.readouterr().err


def test_add_visit_puts_clips_in_the_dataset(tmp_path, capsys):
    clip = write_clip(tmp_path / "found.mp4", [100] * 4)
    config = write_config(tmp_path)
    assert main(["add-visit", "poop", str(clip), "--config", str(config)]) == 0
    assert "found.mp4 -> poop/" in capsys.readouterr().out
    assert len(list((tmp_path / "store" / "dataset" / "poop").iterdir())) == 1


def test_add_visit_reports_a_broken_clip(tmp_path, capsys):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"x")
    assert main(["add-visit", "pee", str(bad), "--config", str(write_config(tmp_path))]) == 1
    assert "bad.mp4" in capsys.readouterr().err
