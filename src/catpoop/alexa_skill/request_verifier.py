"""Check that a request to `/alexa` really comes from Alexa, for our skill, just now.

Amazon's rules for skills hosted as a web service:

1. `SignatureCertChainUrl` is `https://s3.amazonaws.com/echo.api/...`, on port 443 if given.
   `..` and `%2e` are resolved first.
2. The chain there leads from a certificate for `echo-api.amazon.com`, valid now, to a root.
   The roots are certifi's list unless tests pass their own.
3. `Signature-256` is that certificate's RSA SHA-256 signature of the raw body.
4. `request.timestamp` is within 150 seconds of now.
5. The skill ID in the request is ours.

Anything else raises `RequestRejected`; the endpoint answers it with HTTP 400.
"""

import base64
import binascii
import json
import posixpath
import re
import warnings
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import unquote, urlsplit

import certifi
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.verification import PolicyBuilder, Store, VerificationError

from catpoop.clock import Clock
from catpoop.interfaces import CertificateSource

ECHO_HOST = "echo-api.amazon.com"
TOLERANCE = timedelta(seconds=150)
_CERT_HOST = "s3.amazonaws.com"
_CERT_PATH = "/echo.api/"
_PEM_BLOCK = rb"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----"


class RequestRejected(Exception):
    """The request is not a fresh, signed Alexa request for our skill."""


def check_cert_url(url: str) -> None:
    """Raise `RequestRejected` unless `url` is a place Amazon keeps its signing chain."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise RequestRejected(f"bad cert chain URL {url!r}") from None
    path = posixpath.normpath(unquote(parts.path)) if parts.path else ""
    if (
        parts.scheme.lower() != "https"
        or (parts.hostname or "").lower() != _CERT_HOST
        or parts.username is not None
        or port not in (None, 443)
        or not path.startswith(_CERT_PATH)
    ):
        raise RequestRejected(f"cert chain URL not allowed: {url!r}")


def default_trust_store() -> Store:
    """The root certificates in certifi's list (Mozilla's).

    Each is loaded on its own, so one that this `cryptography` refuses is skipped.
    Some old roots break RFC 5280, and one bad root must not fail them all.
    """
    with open(certifi.where(), "rb") as file:
        blocks = re.findall(_PEM_BLOCK, file.read(), re.DOTALL)
    roots = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for block in blocks:
            try:
                roots.append(x509.load_pem_x509_certificate(block))
            except ValueError:
                continue
    return Store(roots)


def check_chain(chain_pem: bytes, now: datetime, trusted: Store) -> x509.Certificate:
    """The signing certificate, if `chain_pem` leads from one for Alexa to a trusted root."""
    try:
        certs = x509.load_pem_x509_certificates(chain_pem)
    except ValueError:
        raise RequestRejected("cert chain is not PEM certificates") from None
    leaf, intermediates = certs[0], certs[1:]
    if not _valid_at(leaf, now):
        raise RequestRejected("signing certificate is not valid now")
    try:
        names = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        raise RequestRejected("signing certificate has no host names") from None
    if ECHO_HOST not in names.get_values_for_type(x509.DNSName):
        raise RequestRejected(f"signing certificate is not for {ECHO_HOST}")
    verifier = (
        PolicyBuilder().store(trusted).time(now).build_server_verifier(x509.DNSName(ECHO_HOST))
    )
    try:
        verifier.verify(leaf, intermediates)
    except VerificationError as error:
        raise RequestRejected(f"cert chain does not lead to a trusted root: {error}") from None
    return leaf


def check_signature(leaf: x509.Certificate, signature: str, body: bytes) -> None:
    """Raise `RequestRejected` unless `signature` (base64) signs `body` with `leaf`'s key."""
    try:
        raw = base64.b64decode(signature, validate=True)
    except (binascii.Error, ValueError):
        raise RequestRejected("signature is not base64") from None
    key = leaf.public_key()
    if not isinstance(key, rsa.RSAPublicKey):
        raise RequestRejected("signing certificate has no RSA key")
    try:
        key.verify(raw, body, padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature:
        raise RequestRejected("signature does not match the body") from None


def check_timestamp(request: Mapping[str, Any], now: datetime) -> None:
    """Raise `RequestRejected` unless `request.timestamp` is within 150 s of `now`."""
    stamp = (request.get("request") or {}).get("timestamp")
    try:
        at = datetime.fromisoformat(stamp) if isinstance(stamp, str) else None
    except ValueError:
        at = None
    if at is None or at.tzinfo is None:
        raise RequestRejected(f"unreadable timestamp {stamp!r}")
    if abs(now - at) > TOLERANCE:
        raise RequestRejected(f"timestamp {stamp} is more than 150 s from now")


def check_skill_id(request: Mapping[str, Any], skill_id: str) -> None:
    """Raise `RequestRejected` unless every skill ID in `request` is `skill_id`."""
    found = [
        _dig(request, "context", "System", "application", "applicationId"),
        _dig(request, "session", "application", "applicationId"),
    ]
    present = [value for value in found if value is not None]
    if not present or any(value != skill_id for value in present):
        raise RequestRejected("request is not for this skill")


class RequestVerifier:
    """Checks every rule in the module docstring; caches signing certificates that signed."""

    def __init__(
        self,
        skill_id: str,
        certificates: CertificateSource,
        clock: Clock,
        trusted: Store | None = None,
    ) -> None:
        """Accept requests for `skill_id` only, fetching chains from `certificates`."""
        if not skill_id:
            raise ValueError("the Alexa skill ID must be set")
        self._skill_id = skill_id
        self._certificates = certificates
        self._clock = clock
        self._trusted = trusted or default_trust_store()
        self._leaves: dict[str, x509.Certificate] = {}

    def verify(self, headers: Mapping[str, str], body: bytes) -> dict[str, Any]:
        """The request as JSON, or raise `RequestRejected`."""
        named = {name.lower(): value for name, value in headers.items()}
        url = named.get("signaturecertchainurl")
        signature = named.get("signature-256")
        if not url or not signature:
            raise RequestRejected("no SignatureCertChainUrl or Signature-256 header")
        check_cert_url(url)
        now = self._clock.now()
        leaf = self._leaf(url, now)
        check_signature(leaf, signature, body)
        self._leaves[url] = leaf  # kept only once Amazon's signature proves the URL is real
        try:
            request = json.loads(body)
        except ValueError:
            raise RequestRejected("body is not JSON") from None
        if not isinstance(request, dict):
            raise RequestRejected("body is not a JSON object")
        check_timestamp(request, now)
        check_skill_id(request, self._skill_id)
        return request

    def _leaf(self, url: str, now: datetime) -> x509.Certificate:
        leaf = self._leaves.get(url)
        if leaf is not None and _valid_at(leaf, now):
            return leaf
        try:
            chain = self._certificates.fetch(url)
        except OSError as error:
            raise RequestRejected(f"cannot fetch the cert chain: {error}") from None
        return check_chain(chain, now, self._trusted)


def _valid_at(cert: x509.Certificate, now: datetime) -> bool:
    return cert.not_valid_before_utc <= now <= cert.not_valid_after_utc


def _dig(data: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data
