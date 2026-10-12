import pytest
from test_service_installer import FakeServiceManager

from catpoop.cli import main
from catpoop.service.command import Places, run_service
from catpoop.service.settings import ServiceSetupError
from catpoop.service.unit_file import UNIT_NAME


@pytest.fixture
def places(tmp_path):
    return Places(
        unit_folder=tmp_path / "units",
        secrets_file=tmp_path / "catpoop" / "service.env",
        linger_folder=tmp_path / "linger",
    )


@pytest.fixture
def checkout(tmp_path):
    folder = tmp_path / "checkout"
    folder.mkdir()
    (folder / "config.toml").write_text("")
    return folder


def _which(found):
    return lambda name: found.get(name)


def test_show_prints_the_unit_and_changes_nothing(checkout, places, capsys):
    manager = FakeServiceManager()
    code = run_service(
        "show", checkout, "cpu", [], places, manager, _which({"uv": "/opt/uv"}), user="u"
    )
    assert code == 0
    assert f"WorkingDirectory={checkout}" in capsys.readouterr().out
    assert manager.calls == []
    assert not places.unit_folder.exists()


def test_install_writes_starts_and_says_where_logs_are(checkout, places, capsys):
    manager = FakeServiceManager()
    code = run_service(
        "install", checkout, "cpu", ["google"], places, manager, _which({"uv": "/opt/uv"}), "u"
    )
    assert code == 0
    unit = (places.unit_folder / UNIT_NAME).read_text()
    assert "--extra google" in unit
    assert ("enable_and_restart", UNIT_NAME, "True") in manager.calls
    out = capsys.readouterr().out
    assert "journalctl --user -u catpoop" in out
    assert "loginctl enable-linger" in out


def test_install_with_linger_on_does_not_ask_for_it(checkout, places, capsys):
    (places.linger_folder).mkdir()
    (places.linger_folder / "u").write_text("")
    run_service(
        "install", checkout, "cpu", [], places, FakeServiceManager(), _which({"uv": "/u"}), "u"
    )
    assert "enable-linger" not in capsys.readouterr().out


def test_install_with_op_stops_before_starting_without_a_service_account_token(
    checkout, places, capsys
):
    (checkout / ".env").write_text("A=op://v/i/f\n")
    which = _which({"uv": "/opt/uv", "op": "/opt/op"})
    manager = FakeServiceManager()
    code = run_service("install", checkout, "cpu", [], places, manager, which, "u")
    err = capsys.readouterr().err
    assert code == 1
    assert manager.calls == []
    assert "OP_SERVICE_ACCOUNT_TOKEN" in err
    assert str(places.secrets_file) in err


def test_install_with_op_and_a_service_account_token_starts(checkout, places):
    (checkout / ".env").write_text("A=op://v/i/f\n")
    places.secrets_file.parent.mkdir()
    places.secrets_file.write_text("OP_SERVICE_ACCOUNT_TOKEN=x\n")
    which = _which({"uv": "/opt/uv", "op": "/opt/op"})
    manager = FakeServiceManager()
    assert run_service("install", checkout, "cpu", [], places, manager, which, "u") == 0
    assert ("enable_and_restart", UNIT_NAME, "True") in manager.calls


def test_install_warns_when_the_checkout_has_no_config(tmp_path, places, capsys):
    which = _which({"uv": "/opt/uv"})
    run_service("install", tmp_path, "cpu", [], places, FakeServiceManager(), which, "u")
    assert "config.toml" in capsys.readouterr().err


def test_uninstall(checkout, places, capsys):
    which = _which({"uv": "/opt/uv"})
    run_service("install", checkout, "cpu", [], places, FakeServiceManager(), which, "u")
    manager = FakeServiceManager()
    assert run_service("uninstall", checkout, "cpu", [], places, manager, which, "u") == 0
    assert not (places.unit_folder / UNIT_NAME).exists()
    assert "Removed" in capsys.readouterr().out
    assert run_service("uninstall", checkout, "cpu", [], places, manager, which, "u") == 0
    assert "not installed" in capsys.readouterr().out


def test_errors_are_readable(checkout, places, capsys):
    class Failing(FakeServiceManager):
        def reload(self):
            raise ServiceSetupError("no systemd here")

    code = run_service("install", checkout, "cpu", [], places, Failing(), _which({"uv": "/u"}))
    assert code == 1
    assert "no systemd here" in capsys.readouterr().err


def test_cli_show(checkout, tmp_path, monkeypatch, capsys):
    bin_folder = tmp_path / "bin"
    bin_folder.mkdir()
    (bin_folder / "uv").write_text("#!/bin/sh\n")
    (bin_folder / "uv").chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_folder))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert main(["service", "show", "--checkout", str(checkout), "--extra", "google"]) == 0
    assert "--extra google" in capsys.readouterr().out
