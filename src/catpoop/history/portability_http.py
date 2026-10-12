"""The real Data Portability API client, over HTTPS with an OAuth refresh token.

Secrets come from the environment (`.env`): `CATPOOP_PORTABILITY_REFRESH_TOKEN`, and
`CATPOOP_PORTABILITY_CLIENT_ID`/`_CLIENT_SECRET` (default: the camera's
`GOOGLENESTCAM_CLIENT_ID`/`_CLIENT_SECRET`). See docs/history-import.md.
"""

import os
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

import httpx

from catpoop.config import ConfigError
from catpoop.interfaces import ArchiveState, PortabilityError

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_API = "https://dataportability.googleapis.com/v1"


def _rfc3339(when: datetime) -> str:
    return when.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _check(response: httpx.Response) -> httpx.Response:
    if response.is_error:
        response.read()
        try:
            reason = response.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            reason = response.text[:200]
        raise PortabilityError(f"{response.request.url.path}: {response.status_code} {reason}")
    return response


class PortabilityHttpApi:
    """Talks to `dataportability.googleapis.com`."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        http: httpx.Client | None = None,
    ) -> None:
        """Use the OAuth client and refresh token given."""
        self.client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._http = http or httpx.Client(timeout=60)
        self._token = ""
        self._token_expires = 0.0

    @classmethod
    def from_env(cls) -> Self:
        """Build from environment variables, or raise `ConfigError` naming what is missing."""
        env = os.environ
        own = env.get("CATPOOP_PORTABILITY_CLIENT_ID") or env.get(
            "CATPOOP_PORTABILITY_CLIENT_SECRET"
        )
        client = "CATPOOP_PORTABILITY" if own else "GOOGLENESTCAM"
        values = {
            "client id": env.get(f"{client}_CLIENT_ID"),
            "client secret": env.get(f"{client}_CLIENT_SECRET"),
            "refresh token": env.get("CATPOOP_PORTABILITY_REFRESH_TOKEN"),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ConfigError(
                f"Data Portability {', '.join(missing)} not set; set "
                "CATPOOP_PORTABILITY_REFRESH_TOKEN (and CATPOOP_PORTABILITY_CLIENT_ID/_SECRET "
                "or GOOGLENESTCAM_CLIENT_ID/_SECRET) in .env"
            )
        client_id, client_secret, refresh_token = (str(value) for value in values.values())
        return cls(client_id, client_secret, refresh_token)

    def _headers(self) -> dict[str, str]:
        if time.monotonic() >= self._token_expires:
            body = _check(
                self._http.post(
                    _TOKEN_URL,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self._client_secret,
                        "refresh_token": self._refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
            ).json()
            self._token = body["access_token"]
            self._token_expires = time.monotonic() + int(body.get("expires_in", 3600)) - 60
        return {"Authorization": f"Bearer {self._token}"}

    def initiate(
        self, resources: Sequence[str], start: datetime | None, end: datetime | None
    ) -> str:
        """Start exporting `resources` and return the archive job id."""
        body: dict[str, Any] = {"resources": list(resources)}
        if start:
            body["startTime"] = _rfc3339(start)
        if end:
            body["endTime"] = _rfc3339(end)
        url = f"{_API}/portabilityArchive:initiate"
        response = _check(self._http.post(url, json=body, headers=self._headers()))
        return response.json()["archiveJobId"]

    def state(self, job_id: str) -> ArchiveState:
        """The job's current state."""
        url = f"{_API}/archiveJobs/{job_id}/portabilityArchiveState"
        body = _check(self._http.get(url, headers=self._headers())).json()
        return ArchiveState(body["state"], list(body.get("urls", [])))

    def download(self, url: str, to: Path) -> None:
        """Save the archive at the signed `url` to `to` (no token is sent)."""
        with self._http.stream("GET", url) as response, to.open("wb") as file:
            _check(response)
            for chunk in response.iter_bytes():
                file.write(chunk)
