import threading

import httpx
import pytest

from catpoop.alexa_skill.endpoint import MAX_BODY, EndpointResponse
from catpoop.alexa_skill.server import make_server


class Endpoint:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict, bytes]] = []

    def handle(self, method, path, headers, body) -> EndpointResponse:
        self.calls.append((method, path, dict(headers), body))
        return EndpointResponse(200, b'{"ok": true}', "application/json;charset=UTF-8")


@pytest.fixture
def served():
    endpoint = Endpoint()
    server = make_server(endpoint, "127.0.0.1", 0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
            yield endpoint, client
    finally:
        server.shutdown()
        server.server_close()


def test_requests_are_handed_to_the_endpoint_with_headers_and_body(served):
    endpoint, client = served
    response = client.post("/alexa", content=b"{}", headers={"Signature-256": "abc"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json;charset=UTF-8"
    assert response.json() == {"ok": True}
    method, path, headers, body = endpoint.calls[0]
    assert (method, path, body) == ("POST", "/alexa", b"{}")
    assert {k.lower(): v for k, v in headers.items()}["signature-256"] == "abc"


def test_get_and_other_methods_reach_the_endpoint_too(served):
    endpoint, client = served
    client.get("/")
    client.put("/alexa", content=b"x")
    assert [(m, p) for m, p, _, _ in endpoint.calls] == [("GET", "/"), ("PUT", "/alexa")]


def test_a_body_over_the_limit_is_413_and_not_handed_on(served):
    endpoint, client = served
    response = client.post("/alexa", content=b"x" * (MAX_BODY + 1))
    assert response.status_code == 413
    assert endpoint.calls == []


def test_the_server_does_not_say_what_it_runs(served):
    _, client = served
    assert "Python" not in client.post("/alexa", content=b"{}").headers.get("server", "")
