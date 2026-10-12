import httpx
import pytest

from catpoop.alexa_skill.certificates import HttpCertificates

URL = "https://s3.amazonaws.com/echo.api/echo-api-cert.pem"


def client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_the_chain_is_the_body_at_the_url():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, content=b"PEM")

    assert HttpCertificates(client(handler)).fetch(URL) == b"PEM"
    assert seen == [URL]


@pytest.mark.parametrize("status", [301, 403, 404, 500])
def test_anything_but_200_is_an_error(status):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, headers={"Location": "https://evil.example/"})

    with pytest.raises(OSError):
        HttpCertificates(client(handler)).fetch(URL)


def test_a_network_failure_is_an_os_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(OSError):
        HttpCertificates(client(handler)).fetch(URL)


def test_a_huge_body_is_refused():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 200_000)

    with pytest.raises(OSError):
        HttpCertificates(client(handler)).fetch(URL)
