"""Speaker kind "voice_monkey": an Alexa device, through the Voice Monkey announce API.

The Voice Monkey token comes from `CATPOOP_VOICE_MONKEY_TOKEN` in `.env`; it is
never logged or put in error messages.
"""

import os
from collections.abc import Mapping
from typing import Any

import httpx

from catpoop.config import Config, ConfigError
from catpoop.registry import DEFAULT, SPEAKER

TOKEN_ENV = "CATPOOP_VOICE_MONKEY_TOKEN"
_ANNOUNCE = "https://api-v3.voicemonkey.io/announce"


class VoiceMonkeyError(Exception):
    """Voice Monkey did not take the Announcement."""


class VoiceMonkeySpeaker:
    """Says text on one Voice Monkey Speaker device, in an Amazon voice."""

    def __init__(
        self,
        name: str,
        device: str,
        token: str,
        http: httpx.Client | None = None,
        voice: str | None = None,
        chime: str | None = None,
    ) -> None:
        """Speak on `device` (its id in the Voice Monkey console) with `token`."""
        self.name = name
        self.device = device
        self._token = token
        self._http = http or httpx.Client(timeout=10)
        self._extra = {k: v for k, v in {"voice": voice, "chime": chime}.items() if v}

    def __repr__(self) -> str:
        """Name and device, never the token."""
        return f"VoiceMonkeySpeaker(name={self.name!r}, device={self.device!r})"

    def say(self, text: str) -> None:
        """Announce `text`, or raise `VoiceMonkeyError`."""
        try:
            response = self._http.post(
                _ANNOUNCE,
                headers={"Authorization": f"Bearer {self._token}"},
                json={"device": self.device, "speech": text, **self._extra},
            )
        except httpx.HTTPError as error:
            # Drop the cause: its message or request could carry the token.
            raise VoiceMonkeyError(f"Voice Monkey: {type(error).__name__}") from None
        if response.is_error:
            raise VoiceMonkeyError(f"Voice Monkey: {response.status_code} for {self.device!r}")
        try:
            answer = response.json()
        except ValueError:
            return
        if isinstance(answer, dict) and answer.get("success") is False:
            reason = str(answer.get("error", "refused"))[:200]
            raise VoiceMonkeyError(f"Voice Monkey: {reason} for {self.device!r}")


@DEFAULT.part(SPEAKER, "voice_monkey")
def _create(config: Config, options: Mapping[str, Any]) -> VoiceMonkeySpeaker:
    token = os.environ.get(TOKEN_ENV)
    if not token:
        raise ConfigError(f"speaker {options['name']!r}: set {TOKEN_ENV} in .env")
    device = options.get("device")
    if not device:
        raise ConfigError(f"speaker {options['name']!r}: device (Voice Monkey device id) missing")
    return VoiceMonkeySpeaker(
        options["name"], device, token, voice=options.get("voice"), chime=options.get("chime")
    )
