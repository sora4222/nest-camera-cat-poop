from pathlib import Path

from catpoop.cli import main

REPO = Path(__file__).resolve().parent.parent


def test_check_config_accepts_example_and_lists_parts(capsys):
    assert main(["check-config", "--config", str(REPO / "config.example.toml")]) == 0
    out = capsys.readouterr().out
    assert "presence: off (available)" in out
    assert "camera: nest (available)" in out
    assert "communications: standard (available)" in out


def test_check_config_reports_bad_file(tmp_path, capsys):
    bad = tmp_path / "config.toml"
    bad.write_text("[parts]\n")
    assert main(["check-config", "--config", str(bad)]) == 1
    assert "camera" in capsys.readouterr().err
