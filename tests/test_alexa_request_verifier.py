from datetime import UTC, datetime

import pytest
from cryptography.x509.verification import Store
from fake_clock import FakeClock

from catpoop.alexa_skill import request_verifier
from catpoop.alexa_skill.request_verifier import (
    RequestRejected,
    RequestVerifier,
    check_cert_url,
)

SKILL_ID = "amzn1.ask.skill.00000000-0000-0000-0000-000000000000"


class Certificates:
    def __init__(self, chains: dict[str, bytes]) -> None:
        self.chains = chains
        self.fetched: list[str] = []

    def fetch(self, url: str) -> bytes:
        self.fetched.append(url)
        if url not in self.chains:
            raise OSError(f"cannot fetch {url}")
        return self.chains[url]


# Cert chain URL rules


@pytest.mark.parametrize(
    "url",
    [
        "https://s3.amazonaws.com/echo.api/echo-api-cert.pem",
        "HTTPS://s3.amazonaws.com/echo.api/echo-api-cert.pem",
        "https://S3.AMAZONAWS.COM/echo.api/echo-api-cert.pem",
        "https://s3.amazonaws.com:443/echo.api/echo-api-cert.pem",
        "https://s3.amazonaws.com/echo.api/../echo.api/echo-api-cert.pem",
    ],
)
def test_amazons_cert_urls_are_allowed(url):
    check_cert_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://s3.amazonaws.com/echo.api/echo-api-cert.pem",
        "https://notamazon.com/echo.api/echo-api-cert.pem",
        "https://s3.amazonaws.com.evil.example/echo.api/echo-api-cert.pem",
        "https://s3.amazonaws.com/EcHo.aPi/echo-api-cert.pem",
        "https://s3.amazonaws.com/invalid.path/echo-api-cert.pem",
        "https://s3.amazonaws.com:563/echo.api/echo-api-cert.pem",
        "https://s3.amazonaws.com/echo.api/../invalid.path/echo-api-cert.pem",
        "https://s3.amazonaws.com/echo.api/%2e%2e/invalid.path/echo-api-cert.pem",
        "https://someone@s3.amazonaws.com/echo.api/echo-api-cert.pem",
        "https://s3.amazonaws.com:notaport/echo.api/echo-api-cert.pem",
        "https://s3.amazonaws.com/echo.api",
        "",
    ],
)
def test_other_cert_urls_are_rejected(url):
    with pytest.raises(RequestRejected):
        check_cert_url(url)


def test_the_skill_id_must_be_set():
    with pytest.raises(ValueError):
        RequestVerifier("", Certificates({}), FakeClock(datetime(2026, 10, 11, 10, 0, tzinfo=UTC)))


def test_the_default_trust_store_is_read_from_certifi():
    from catpoop.alexa_skill.request_verifier import default_trust_store

    assert isinstance(default_trust_store(), Store)


class Leaf:
    not_valid_before_utc = datetime(2026, 1, 1, tzinfo=UTC)
    not_valid_after_utc = datetime(2027, 1, 1, tzinfo=UTC)


def test_a_signing_certificate_is_kept_only_after_a_signature_matches(monkeypatch):
    def check_signature(leaf, signature: str, body: bytes) -> None:
        if signature != "good":
            raise RequestRejected("signature does not match the body")

    monkeypatch.setattr(request_verifier, "check_chain", lambda chain, now, trusted: Leaf())
    monkeypatch.setattr(request_verifier, "check_signature", check_signature)
    url = "https://s3.amazonaws.com/echo.api/echo-api-cert.pem"
    certificates = Certificates({f"{url}#{n}": b"pem" for n in range(2)} | {url: b"pem"})
    clock = FakeClock(datetime(2026, 10, 11, 10, 0, tzinfo=UTC))
    verifier = RequestVerifier(SKILL_ID, certificates, clock)
    for forged in (f"{url}#0", f"{url}#1", f"{url}#0"):
        with pytest.raises(RequestRejected):
            verifier.verify({"SignatureCertChainUrl": forged, "Signature-256": "bad"}, b"{}")
    for _ in range(2):
        with pytest.raises(RequestRejected, match="timestamp"):
            verifier.verify({"SignatureCertChainUrl": url, "Signature-256": "good"}, b"{}")
    assert certificates.fetched == [f"{url}#0", f"{url}#1", f"{url}#0", url]
    assert list(verifier._leaves) == [url]
