import json
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.x509.verification import Store
from fake_amazon_certs import ECHO_HOST, NOW, FakeAmazon, make_fake_amazon, pem
from fake_clock import FakeClock

from catpoop.alexa_skill import request_verifier
from catpoop.alexa_skill.request_verifier import (
    RequestRejected,
    RequestVerifier,
    check_cert_url,
)

SKILL_ID = "amzn1.ask.skill.00000000-0000-0000-0000-000000000000"
CERT_URL = "https://s3.amazonaws.com/echo.api/echo-api-cert.pem"


@pytest.fixture(scope="module")
def amazon() -> FakeAmazon:
    return make_fake_amazon()


class Certificates:
    def __init__(self, chains: dict[str, bytes]) -> None:
        self.chains = chains
        self.fetched: list[str] = []

    def fetch(self, url: str) -> bytes:
        self.fetched.append(url)
        if url not in self.chains:
            raise OSError(f"cannot fetch {url}")
        return self.chains[url]


def request(at=NOW, skill_id=SKILL_ID, session_skill_id=None) -> dict:
    body = {
        "version": "1.0",
        "context": {"System": {"application": {"applicationId": skill_id}}},
        "request": {
            "type": "LaunchRequest",
            "requestId": "amzn1.echo-api.request.1",
            "timestamp": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "locale": "en-US",
        },
    }
    if session_skill_id is not None:
        body["session"] = {"application": {"applicationId": session_skill_id}}
    return body


def make(amazon: FakeAmazon, chain: bytes | None = None, clock=None, root=None):
    certificates = Certificates({CERT_URL: amazon.chain if chain is None else chain})
    verifier = RequestVerifier(
        SKILL_ID,
        certificates,
        clock or FakeClock(NOW),
        trusted=Store([root or amazon.root]),
    )
    return verifier, certificates


def signed(amazon: FakeAmazon, body: dict | bytes, **headers: str):
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    return {
        "SignatureCertChainUrl": CERT_URL,
        "Signature-256": amazon.sign(raw),
        **headers,
    }, raw


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


# A good request


def test_a_signed_fresh_request_for_our_skill_is_accepted(amazon):
    verifier, _ = make(amazon)
    headers, raw = signed(amazon, request())
    assert verifier.verify(headers, raw) == json.loads(raw)


def test_header_names_are_matched_whatever_their_case(amazon):
    verifier, _ = make(amazon)
    headers, raw = signed(amazon, request())
    lower = {name.lower(): value for name, value in headers.items()}
    assert verifier.verify(lower, raw)["request"]["type"] == "LaunchRequest"


def test_the_chain_is_fetched_once_per_url(amazon):
    verifier, certificates = make(amazon)
    for _ in range(3):
        verifier.verify(*signed(amazon, request()))
    assert certificates.fetched == [CERT_URL]


def test_a_cached_chain_is_fetched_again_once_its_certificate_expired(amazon):
    clock = FakeClock(NOW)
    verifier, certificates = make(amazon, clock=clock)
    verifier.verify(*signed(amazon, request()))
    clock.advance(timedelta(days=31).total_seconds())
    with pytest.raises(RequestRejected):
        verifier.verify(*signed(amazon, request(at=clock.now())))
    assert certificates.fetched == [CERT_URL, CERT_URL]


# Headers and signature


def test_missing_signature_headers_are_rejected(amazon):
    verifier, _ = make(amazon)
    headers, raw = signed(amazon, request())
    for name in ("SignatureCertChainUrl", "Signature-256"):
        partial = {k: v for k, v in headers.items() if k != name}
        with pytest.raises(RequestRejected):
            verifier.verify(partial, raw)


def test_a_bad_cert_url_is_rejected_without_fetching_it(amazon):
    verifier, certificates = make(amazon)
    headers, raw = signed(amazon, request())
    headers["SignatureCertChainUrl"] = "https://evil.example/echo.api/cert.pem"
    with pytest.raises(RequestRejected):
        verifier.verify(headers, raw)
    assert certificates.fetched == []


def test_a_chain_that_cannot_be_fetched_is_rejected(amazon):
    verifier, _ = make(amazon)
    headers, raw = signed(amazon, request())
    headers["SignatureCertChainUrl"] = "https://s3.amazonaws.com/echo.api/other.pem"
    with pytest.raises(RequestRejected):
        verifier.verify(headers, raw)


def test_a_changed_body_is_rejected(amazon):
    verifier, _ = make(amazon)
    headers, raw = signed(amazon, request())
    with pytest.raises(RequestRejected):
        verifier.verify(headers, raw.replace(b"LaunchRequest", b"IntentRequest"))


def test_a_body_signed_with_another_key_is_rejected(amazon):
    other = make_fake_amazon()
    verifier, _ = make(amazon)
    raw = json.dumps(request()).encode()
    headers = {"SignatureCertChainUrl": CERT_URL, "Signature-256": other.sign(raw)}
    with pytest.raises(RequestRejected):
        verifier.verify(headers, raw)


def test_a_signature_that_is_not_base64_is_rejected(amazon):
    verifier, _ = make(amazon)
    headers, raw = signed(amazon, request())
    headers["Signature-256"] = "not base64!"
    with pytest.raises(RequestRejected):
        verifier.verify(headers, raw)


def test_only_the_old_sha1_signature_is_not_enough(amazon):
    verifier, _ = make(amazon)
    headers, raw = signed(amazon, request())
    headers["Signature"] = headers.pop("Signature-256")
    with pytest.raises(RequestRejected):
        verifier.verify(headers, raw)


# The certificate chain


def test_a_chain_from_an_untrusted_root_is_rejected(amazon):
    other = make_fake_amazon()
    verifier, _ = make(amazon, root=other.root)
    with pytest.raises(RequestRejected):
        verifier.verify(*signed(amazon, request()))


def test_a_signing_certificate_for_another_host_is_rejected(amazon):
    leaf = amazon.leaf_for(["echo-api.evil.example"])
    verifier, _ = make(amazon, chain=pem(leaf, amazon.intermediate))
    with pytest.raises(RequestRejected):
        verifier.verify(*signed(amazon, request()))


def test_a_signing_certificate_with_no_host_names_is_rejected(amazon):
    leaf = amazon.leaf_for([])
    verifier, _ = make(amazon, chain=pem(leaf, amazon.intermediate))
    with pytest.raises(RequestRejected):
        verifier.verify(*signed(amazon, request()))


def test_an_expired_signing_certificate_is_rejected(amazon):
    leaf = amazon.leaf_for(
        [ECHO_HOST], start=NOW - timedelta(days=60), end=NOW - timedelta(seconds=1)
    )
    verifier, _ = make(amazon, chain=pem(leaf, amazon.intermediate))
    with pytest.raises(RequestRejected):
        verifier.verify(*signed(amazon, request()))


def test_a_not_yet_valid_signing_certificate_is_rejected(amazon):
    leaf = amazon.leaf_for([ECHO_HOST], start=NOW + timedelta(hours=1))
    verifier, _ = make(amazon, chain=pem(leaf, amazon.intermediate))
    with pytest.raises(RequestRejected):
        verifier.verify(*signed(amazon, request()))


def test_a_signing_certificate_signed_by_someone_else_is_rejected(amazon):
    other = make_fake_amazon()
    leaf = amazon.leaf_for([ECHO_HOST], issuer_key=other.intermediate_key)
    verifier, _ = make(amazon, chain=pem(leaf, amazon.intermediate))
    with pytest.raises(RequestRejected):
        verifier.verify(*signed(amazon, request()))


def test_a_chain_missing_its_intermediate_is_rejected(amazon):
    verifier, _ = make(amazon, chain=pem(amazon.leaf))
    with pytest.raises(RequestRejected):
        verifier.verify(*signed(amazon, request()))


def test_a_chain_that_is_not_pem_is_rejected(amazon):
    verifier, _ = make(amazon, chain=b"<html>not found</html>")
    with pytest.raises(RequestRejected):
        verifier.verify(*signed(amazon, request()))


# Timestamp


@pytest.mark.parametrize("seconds", [-150, -10, 0, 10, 150])
def test_a_timestamp_within_150_seconds_is_accepted(amazon, seconds):
    verifier, _ = make(amazon)
    verifier.verify(*signed(amazon, request(at=NOW + timedelta(seconds=seconds))))


@pytest.mark.parametrize("seconds", [-151, -3600, 151, 3600])
def test_a_timestamp_further_off_is_rejected(amazon, seconds):
    verifier, _ = make(amazon)
    with pytest.raises(RequestRejected):
        verifier.verify(*signed(amazon, request(at=NOW + timedelta(seconds=seconds))))


@pytest.mark.parametrize("timestamp", [None, "", "yesterday", 1234, "2026-10-11T10:00:00"])
def test_a_missing_or_unreadable_timestamp_is_rejected(amazon, timestamp):
    verifier, _ = make(amazon)
    body = request()
    if timestamp is None:
        del body["request"]["timestamp"]
    else:
        body["request"]["timestamp"] = timestamp
    with pytest.raises(RequestRejected):
        verifier.verify(*signed(amazon, body))


# Skill ID and body


def test_a_request_for_another_skill_is_rejected(amazon):
    verifier, _ = make(amazon)
    with pytest.raises(RequestRejected):
        verifier.verify(*signed(amazon, request(skill_id="amzn1.ask.skill.someone-else")))


def test_a_session_for_another_skill_is_rejected(amazon):
    verifier, _ = make(amazon)
    body = request(session_skill_id="amzn1.ask.skill.someone-else")
    with pytest.raises(RequestRejected):
        verifier.verify(*signed(amazon, body))


def test_a_session_for_our_skill_is_accepted(amazon):
    verifier, _ = make(amazon)
    verifier.verify(*signed(amazon, request(session_skill_id=SKILL_ID)))


def test_a_request_with_no_skill_id_is_rejected(amazon):
    verifier, _ = make(amazon)
    body = request()
    del body["context"]
    with pytest.raises(RequestRejected):
        verifier.verify(*signed(amazon, body))


@pytest.mark.parametrize("raw", [b"not json", b"[1, 2]", b"\xff\xfe"])
def test_a_signed_body_that_is_not_a_json_object_is_rejected(amazon, raw):
    verifier, _ = make(amazon)
    with pytest.raises(RequestRejected):
        verifier.verify(*signed(amazon, raw))


def test_the_skill_id_must_be_set():
    with pytest.raises(ValueError):
        RequestVerifier("", Certificates({}), FakeClock(NOW))


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
