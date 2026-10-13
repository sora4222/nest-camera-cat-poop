"""Login with Amazon tokens that let this server send events to Alexa.

Alexa hands over a one-time code (AcceptGrant) when the skill is linked; it is traded
for a refresh token, kept in the state folder, and turned into short-lived access
tokens. Client ID and secret are the skill's "Alexa Skill Messaging" ones. Tokens are
never logged.
"""

import json
import os
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from catpoop.clock import Clock
from catpoop.config import ConfigError
from catpoop.state_folder import state_folder

TOKEN_URL = "https://api.amazon.com/auth/o2/token"
CLIENT_ID_ENV = "CATPOOP_ALEXA_CLIENT_ID"
CLIENT_SECRET_ENV = "CATPOOP_ALEXA_CLIENT_SECRET"


class GrantError(Exception):
    """Amazon refused the code or refresh token, or there is none yet."""


class Grants:
    """The saved refresh token and a cached access token."""

    def __init__(
        self, client_id: str, client_secret: str, file: Path, clock: Clock, http: httpx.Client
    ) -> None:
        """Keep the refresh token in `file` (only this user can read it)."""
        self._client = {"client_id": client_id, "client_secret": client_secret}
        self._file = file
        self._clock = clock
        self._http = http
        self._access: tuple[str, datetime] | None = None

    def __repr__(self) -> str:
        """The file only, never a token."""
        return f"Grants(file={str(self._file)!r})"

    def accept(self, code: str) -> None:
        """Trade the AcceptGrant `code` for tokens and save the refresh token."""
        answer = self._token({"grant_type": "authorization_code", "code": code})
        self._file.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self._file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)  # also when the file was already there
        with os.fdopen(fd, "w") as f:
            json.dump({"refresh_token": answer["refresh_token"]}, f)

    def access_token(self) -> str:
        """A valid access token, refreshed when it is about to run out."""
        if self._access and self._clock.now() < self._access[1]:
            return self._access[0]
        try:
            refresh = json.loads(self._file.read_text())["refresh_token"]
        except (OSError, ValueError, KeyError):
            raise GrantError("not linked yet: enable the skill in the Alexa app") from None
        self._token({"grant_type": "refresh_token", "refresh_token": refresh})
        assert self._access
        return self._access[0]

    @classmethod
    def from_env(cls, environ: Mapping[str, str], clock: Clock) -> "Grants":
        """The skill's messaging client from `.env`, saving to the state folder."""
        client_id = environ.get(CLIENT_ID_ENV, "").strip()
        secret = environ.get(CLIENT_SECRET_ENV, "").strip()
        if not client_id or not secret:
            raise ConfigError(f"Alexa Smart Home: set {CLIENT_ID_ENV} and {CLIENT_SECRET_ENV}")
        file = state_folder() / "alexa-grant.json"
        return cls(client_id, secret, file, clock, httpx.Client(timeout=10))

    def _token(self, form: dict[str, str]) -> dict:
        try:
            response = self._http.post(TOKEN_URL, data={**form, **self._client})
        except httpx.HTTPError as error:
            raise GrantError(f"Login with Amazon: {type(error).__name__}") from None
        if response.is_error:
            raise GrantError(f"Login with Amazon: {response.status_code}")
        answer = response.json()
        expires = self._clock.now() + timedelta(seconds=int(answer["expires_in"]) - 60)
        self._access = (answer["access_token"], expires)
        return answer
