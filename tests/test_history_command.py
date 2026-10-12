import json
import zipfile
from pathlib import Path

from catpoop.cli import main


def write_config(tmp_path: Path, extra: str = "") -> Path:
    path = tmp_path / "config.toml"
    path.write_text(
        f"""
[parts]
camera = "fake"
detector = "fake"
event_rules = "fake"
event_log = "memory"
presence = "off"
communications = "fake"

[paths]
private_data_store = "{tmp_path / "store"}"
{extra}
"""
    )
    return path


def clips_in(tmp_path: Path) -> list[Path]:
    return sorted((tmp_path / "store" / "history" / "clips").glob("*.mp4"))


def test_imports_a_takeout_archive(tmp_path, capsys):
    archive = tmp_path / "takeout-001.zip"
    with zipfile.ZipFile(archive, "w") as out:
        out.writestr("Takeout/Nest/a.mp4", b"a")
        out.writestr("Takeout/Nest/b.mp4", b"b")
    config = write_config(tmp_path)
    assert main(["import-history", "takeout", str(archive), "--config", str(config)]) == 0
    assert "2 new, 0 already stored" in capsys.readouterr().out
    assert len(clips_in(tmp_path)) == 2
    assert main(["import-history", "takeout", str(archive), "--config", str(config)]) == 0
    assert "0 new, 2 already stored" in capsys.readouterr().out


def test_paths_can_come_from_config(tmp_path, capsys):
    folder = tmp_path / "saved"
    folder.mkdir()
    (folder / "clip.mp4").write_bytes(b"c")
    config = write_config(tmp_path, f'[history.folder]\npaths = ["{folder}"]\n')
    assert main(["import-history", "folder", "--config", str(config)]) == 0
    (clip,) = clips_in(tmp_path)
    record = json.loads(clip.with_suffix(".json").read_text())
    assert record["sources"][0]["origin"] == "saved/clip.mp4"


def test_problems_are_reported(tmp_path, capsys):
    config = write_config(tmp_path)
    assert main(["import-history", "folder", "--config", str(config)]) == 1
    assert "paths" in capsys.readouterr().err
    assert (
        main(["import-history", "takeout", str(tmp_path / "x.rar"), "--config", str(config)]) == 1
    )
    assert "x.rar" in capsys.readouterr().err


def test_damaged_archives_are_reported(tmp_path, capsys):
    config = write_config(tmp_path)
    for name in ["broken.zip", "broken.tgz"]:
        (tmp_path / name).write_bytes(b"not an archive")
        args = ["import-history", "takeout", str(tmp_path / name), "--config", str(config)]
        assert main(args) == 1
        assert capsys.readouterr().err
