import zipfile
from pathlib import Path

import pytest

from catpoop.config import Config, ConfigError
from catpoop.history.folder import FolderImporter
from catpoop.history.takeout import TakeoutImporter
from catpoop.registry import DEFAULT, HISTORY_IMPORTER


def config(tmp_path: Path, history: dict | None = None) -> Config:
    return Config.model_validate(
        {
            "parts": dict.fromkeys(
                ["camera", "detector", "event_rules", "event_log", "presence", "communications"],
                "fake",
            ),
            "paths": {"private_data_store": str(tmp_path / "store")},
            "history": history or {},
        }
    )


def zip_with(path: Path, names: list[str]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name in names:
            archive.writestr(name, b"x")
    return path


def test_takeout_reads_every_archive_part(tmp_path):
    one = zip_with(tmp_path / "takeout-001.zip", ["Takeout/Nest/a.mp4"])
    two = zip_with(tmp_path / "takeout-002.zip", ["Takeout/Nest/b.mp4"])
    clips = list(TakeoutImporter([one, two]).clips())
    assert [c.origin for c in clips] == [
        "takeout-001.zip!Takeout/Nest/a.mp4",
        "takeout-002.zip!Takeout/Nest/b.mp4",
    ]
    assert {c.source for c in clips} == {"takeout"}


def test_folder_reads_clips_saved_by_hand(tmp_path):
    folder = tmp_path / "saved"
    (folder / "march").mkdir(parents=True)
    (folder / "march" / "clip.mp4").write_bytes(b"x")
    (clip,) = FolderImporter([folder]).clips()
    assert (clip.source, clip.origin) == ("folder", "saved/march/clip.mp4")


def test_folder_must_be_a_folder(tmp_path):
    with pytest.raises(ValueError, match="not a folder"):
        list(FolderImporter([tmp_path / "missing"]).clips())


@pytest.mark.parametrize("name", ["takeout", "folder"])
def test_registered_with_paths_from_options(tmp_path, name):
    importer = DEFAULT.create(HISTORY_IMPORTER, name, config(tmp_path), {"paths": [str(tmp_path)]})
    assert isinstance(importer, (TakeoutImporter, FolderImporter))
    assert importer.paths == [tmp_path]


@pytest.mark.parametrize("name", ["takeout", "folder"])
def test_paths_are_required(tmp_path, name):
    with pytest.raises(ConfigError, match="paths"):
        DEFAULT.create(HISTORY_IMPORTER, name, config(tmp_path), {})


def test_history_options_come_from_config(tmp_path):
    loaded = config(tmp_path, {"takeout": {"paths": ["/exports"]}})
    assert loaded.history["takeout"] == {"paths": ["/exports"]}
