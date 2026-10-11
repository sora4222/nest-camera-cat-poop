import json
from datetime import UTC, datetime

import httpx
import pytest

from catpoop.config import ConfigError
from catpoop.history.portability_api import ArchiveState, PortabilityError
from catpoop.history.portability_http import PortabilityHttpApi

API = "https://dataportability.googleapis.com/v1"


class Google:
    """A fake of Google's token endpoint, Data Portability API and archive storage."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.token_calls = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        if url == "https://oauth2.googleapis.com/token":
            self.token_calls += 1
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        if url.startswith("https://storage.example/"):
            assert "authorization" not in request.headers
            return httpx.Response(200, content=b"zipbytes")
        assert request.headers["authorization"] == "Bearer tok"
        if url == f"{API}/portabilityArchive:initiate":
            return httpx.Response(200, json={"archiveJobId": "job-1"})
        if url == f"{API}/archiveJobs/job-1/portabilityArchiveState":
            return httpx.Response(
                200, json={"state": "COMPLETE", "urls": ["https://storage.example/a"]}
            )
        return httpx.Response(403, json={"error": {"message": "not available in your country"}})


@pytest.fixture
def google():
    return Google()


@pytest.fixture
def api(google):
    client = httpx.Client(transport=httpx.MockTransport(google.handle))
    return PortabilityHttpApi("id", "secret", "refresh", client)


def test_initiate_sends_resources_and_times(api, google):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    assert api.initiate(["nest.camera_event"], start, None) == "job-1"
    token, initiate = google.requests
    assert b"refresh_token=refresh" in token.content
    assert json.loads(initiate.content) == {
        "resources": ["nest.camera_event"],
        "startTime": "2026-01-01T00:00:00Z",
    }


def test_access_token_is_reused(api, google):
    api.initiate(["nest.camera_event"], None, None)
    api.state("job-1")
    assert google.token_calls == 1


def test_state(api):
    assert api.state("job-1") == ArchiveState("COMPLETE", ["https://storage.example/a"])


def test_download_needs_no_token(api, tmp_path):
    to = tmp_path / "part.zip"
    api.download("https://storage.example/a", to)
    assert to.read_bytes() == b"zipbytes"


def test_api_error_is_readable(api):
    with pytest.raises(PortabilityError, match=r"403 .*not available in your country"):
        api.state("other")


def test_from_env_needs_a_refresh_token(monkeypatch):
    monkeypatch.delenv("CATPOOP_PORTABILITY_REFRESH_TOKEN", raising=False)
    monkeypatch.setenv("GOOGLENESTCAM_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLENESTCAM_CLIENT_SECRET", "secret")
    with pytest.raises(ConfigError, match="CATPOOP_PORTABILITY_REFRESH_TOKEN"):
        PortabilityHttpApi.from_env()


def test_from_env_falls_back_to_the_camera_client(monkeypatch):
    monkeypatch.delenv("CATPOOP_PORTABILITY_CLIENT_ID", raising=False)
    monkeypatch.delenv("CATPOOP_PORTABILITY_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("GOOGLENESTCAM_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLENESTCAM_CLIENT_SECRET", "secret")
    monkeypatch.setenv("CATPOOP_PORTABILITY_REFRESH_TOKEN", "refresh")
    assert PortabilityHttpApi.from_env().client_id == "id"
