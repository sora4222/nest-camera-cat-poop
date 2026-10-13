from pathlib import Path

import pytest

from catpoop.service.settings import ServiceSetupError, find_settings


def _which(found: dict[str, str]):
    return lambda name: found.get(name)


def test_finds_uv_op_and_the_env_file(tmp_path):
    (tmp_path / ".env").write_text("A=op://vault/item/field\n")
    secrets = tmp_path / "service.env"
    settings = find_settings(
        tmp_path, "cpu", ("google",), secrets, _which({"uv": "/opt/uv", "op": "/opt/op"})
    )
    assert settings.checkout == tmp_path.resolve()
    assert settings.uv == Path("/opt/uv")
    assert settings.op == Path("/opt/op")
    assert settings.env_file == tmp_path.resolve() / ".env"
    assert settings.extras == ("google",)
    assert settings.secrets_file == secrets


def test_no_env_file_and_no_op(tmp_path):
    settings = find_settings(tmp_path, "cpu", (), tmp_path / "s.env", _which({"uv": "/opt/uv"}))
    assert settings.env_file is None
    assert settings.op is None


def test_needs_uv(tmp_path):
    with pytest.raises(ServiceSetupError, match="uv"):
        find_settings(tmp_path, "cpu", (), tmp_path / "s.env", _which({}))
