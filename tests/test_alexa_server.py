import threading
import time

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
    client.patch("/alexa", content=b"x")
    client.options("/other")
    assert [(m, p) for m, p, _, _ in endpoint.calls] == [
        ("GET", "/"),
        ("PUT", "/alexa"),
        ("PATCH", "/alexa"),
        ("OPTIONS", "/other"),
    ]


def test_a_body_over_the_limit_is_413_and_not_handed_on(served):
    endpoint, client = served
    response = client.post("/alexa", content=b"x" * (MAX_BODY + 1))
    assert response.status_code == 413
    assert endpoint.calls == []


def test_the_server_does_not_say_what_it_runs(served):
    _, client = served
    assert "Python" not in client.post("/alexa", content=b"{}").headers.get("server", "")


def test_the_endpoint_answers_one_request_at_a_time(served):
    endpoint, client = served
    inside, most = [0], [0]
    handle = endpoint.handle

    def slow(*args) -> EndpointResponse:
        inside[0] += 1
        most[0] = max(most[0], inside[0])
        time.sleep(0.05)
        inside[0] -= 1
        return handle(*args)

    endpoint.handle = slow
    port = client.base_url.port
    posts = [
        threading.Thread(
            target=httpx.post, args=(f"http://127.0.0.1:{port}/alexa",), kwargs={"trust_env": False}
        )
        for _ in range(3)
    ]
    for post in posts:
        post.start()
    for post in posts:
        post.join()
    assert len(endpoint.calls) == 3
    assert most[0] == 1
