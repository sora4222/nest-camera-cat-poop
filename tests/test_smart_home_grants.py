import json
import os
from datetime import UTC, datetime

import httpx
import pytest
from fake_clock import FakeClock

from catpoop.alexa_smart_home.grants import CLIENT_ID_ENV, GrantError, Grants
from catpoop.config import ConfigError

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class Amazon:
    def __init__(self) -> None:
        self.forms: list[dict] = []
        self.status = 200

    def handle(self, request: httpx.Request) -> httpx.Response:
        form = dict(httpx.QueryParams(request.content.decode()))
        self.forms.append(form)
        n = len(self.forms)
        answer = {
            "access_token": f"access-{n}",
            "expires_in": 3600,
            "refresh_token": f"refresh-{n}",
        }
        return httpx.Response(self.status, json=answer)


def grants(fake: Amazon, tmp_path, clock=None) -> Grants:
    http = httpx.Client(transport=httpx.MockTransport(fake.handle))
    return Grants("id", "secret", tmp_path / "grant.json", clock or FakeClock(NOW), http)


def test_accept_trades_the_code_and_saves_only_the_refresh_token_privately(tmp_path):
    fake = Amazon()
    grants(fake, tmp_path).accept("code-1")
    assert fake.forms[0] == {
        "grant_type": "authorization_code",
        "code": "code-1",
        "client_id": "id",
        "client_secret": "secret",
    }
    assert json.loads((tmp_path / "grant.json").read_text()) == {"refresh_token": "refresh-1"}
    assert os.stat(tmp_path / "grant.json").st_mode & 0o777 == 0o600


def test_accept_makes_an_existing_file_private_too(tmp_path):
    (tmp_path / "grant.json").write_text("{}")
    os.chmod(tmp_path / "grant.json", 0o644)
    grants(Amazon(), tmp_path).accept("code-1")
    assert os.stat(tmp_path / "grant.json").st_mode & 0o777 == 0o600


def test_access_token_is_refreshed_from_the_saved_token_and_cached(tmp_path):
    fake = Amazon()
    grants(fake, tmp_path).accept("code-1")
    clock = FakeClock(NOW)
    later = grants(fake, tmp_path, clock)
    assert later.access_token() == "access-2"
    assert fake.forms[1]["grant_type"] == "refresh_token"
    assert fake.forms[1]["refresh_token"] == "refresh-1"
    assert later.access_token() == "access-2"
    clock.advance(3600)
    assert later.access_token() == "access-3"


def test_no_saved_token_says_to_link_the_skill(tmp_path):
    with pytest.raises(GrantError, match="not linked"):
        grants(Amazon(), tmp_path).access_token()


def test_refused_code_raises(tmp_path):
    fake = Amazon()
    fake.status = 400
    with pytest.raises(GrantError, match="400"):
        grants(fake, tmp_path).accept("bad")


def test_from_env_needs_the_client(monkeypatch):
    with pytest.raises(ConfigError, match=CLIENT_ID_ENV):
        Grants.from_env({}, FakeClock(NOW))


def test_repr_has_no_secret(tmp_path):
    http = httpx.Client(transport=httpx.MockTransport(Amazon().handle))
    assert "pa55" not in repr(Grants("id", "pa55", tmp_path / "g.json", FakeClock(NOW), http))
