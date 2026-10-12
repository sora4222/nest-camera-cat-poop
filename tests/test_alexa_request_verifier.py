from datetime import UTC, datetime

import pytest
from cryptography.x509.verification import Store
from fake_clock import FakeClock

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
