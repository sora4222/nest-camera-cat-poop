"""Amazon's Alexa web API, the one the Alexa app uses: make an Alexa device say text.

Unofficial, so Amazon may change it. Logs in with a refresh token from the
`alexa-cookie-cli` tool; the token is never logged or put in error messages.
"""

import json
from typing import Any

import httpx


class AlexaWebError(Exception):
    """The Alexa web API refused or could not be reached."""


class AlexaWeb:
    """One logged-in Amazon account, for `amazon.com`, `amazon.com.au` and so on."""

    def __init__(
        self,
        refresh_token: str,
        domain: str = "amazon.com",
        locale: str = "en-US",
        http: httpx.Client | None = None,
    ) -> None:
        """Log in lazily with `refresh_token` on the Amazon site at `domain`."""
        self._token = refresh_token
        self._domain = domain
        self._locale = locale
        self._http = http or httpx.Client(timeout=10)
        self._cookies: dict[str, str] = {}
        self._devices: dict[str, dict[str, Any]] = {}

    def __repr__(self) -> str:
        """Domain only, never the token."""
        return f"AlexaWeb(domain={self._domain!r})"

    def speak(self, device: str, text: str) -> None:
        """Say `text` on the device named `device` in the Alexa app, or raise `AlexaWebError`."""
        try:
            if self._speak(device, text) in (401, 403):
                self._cookies = {}
                if (status := self._speak(device, text)) != 200:
                    raise AlexaWebError(f"Alexa: {status} after logging in again")
        except httpx.HTTPError as error:
            # Drop the cause: its request could carry the token or cookies.
            raise AlexaWebError(f"Alexa: {type(error).__name__}") from None

    def _speak(self, device: str, text: str) -> int:
        if not self._cookies:
            self._log_in()
        found = self._device(device)
        node = {
            "@type": "com.amazon.alexa.behaviors.model.OpaquePayloadOperationNode",
            "type": "Alexa.Speak",
            "operationPayload": {
                "deviceType": found["deviceType"],
                "deviceSerialNumber": found["serialNumber"],
                "customerId": found["deviceOwnerCustomerId"],
                "locale": self._locale,
                "textToSpeak": text,
            },
        }
        sequence = {"@type": "com.amazon.alexa.behaviors.model.Sequence", "startNode": node}
        body = {"behaviorId": "PREVIEW", "sequenceJson": json.dumps(sequence), "status": "ENABLED"}
        response = self._http.post(
            self._url("/api/behaviors/preview"), headers=self._headers(), json=body
        )
        if response.is_error and response.status_code not in (401, 403):
            raise AlexaWebError(f"Alexa: {response.status_code} speaking on {device!r}")
        return response.status_code

    def _log_in(self) -> None:
        response = self._http.post(
            f"https://api.{self._domain}/ap/exchangetoken/cookies",
            headers={"x-amzn-identity-auth-domain": f"api.{self._domain}"},
            data={
                "app_name": "Amazon Alexa",
                "requested_token_type": "auth_cookies",
                "domain": f"www.{self._domain}",
                "source_token_type": "refresh_token",
                "source_token": self._token,
            },
        )
        if response.is_error:
            raise AlexaWebError(f"Alexa: {response.status_code} logging in; renew the token")
        by_domain = response.json()["response"]["tokens"]["cookies"]
        self._cookies = {c["Name"]: c["Value"] for jar in by_domain.values() for c in jar}
        if "csrf" not in self._cookies:
            self._cookies.update(
                self._http.get(self._url("/api/language"), headers=self._headers()).cookies
            )

    def _device(self, name: str) -> dict[str, Any]:
        if name not in self._devices:
            response = self._http.get(
                self._url("/api/devices-v2/device?cached=false"), headers=self._headers()
            )
            if response.is_error:
                raise AlexaWebError(f"Alexa: {response.status_code} listing devices")
            self._devices = {d["accountName"]: d for d in response.json()["devices"]}
        if name not in self._devices:
            raise AlexaWebError(f"Alexa: no device {name!r}; known: {sorted(self._devices)}")
        return self._devices[name]

    def _url(self, path: str) -> str:
        return f"https://alexa.{self._domain}{path}"

    def _headers(self) -> dict[str, str]:
        return {
            "cookie": "; ".join(f"{k}={v}" for k, v in self._cookies.items()),
            "csrf": self._cookies.get("csrf", ""),
            "origin": f"https://alexa.{self._domain}",
            "referer": f"https://alexa.{self._domain}/spa/index.html",
        }
