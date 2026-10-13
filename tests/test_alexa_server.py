import socket

import httpx
import pytest
from fastapi import FastAPI

from catpoop.alexa_skill.server import serving


def app() -> FastAPI:
    served = FastAPI()

    @served.get("/hello")
    def hello() -> dict:
        return {"hello": "world"}

    return served


def test_the_app_is_served_on_a_free_port_inside_the_with():
    with serving(app(), "127.0.0.1", 0) as (host, port):
        assert host == "127.0.0.1"
        assert port > 0
        response = httpx.get(f"http://{host}:{port}/hello", trust_env=False)
    assert response.json() == {"hello": "world"}


def test_the_server_stops_after_the_with():
    with serving(app(), "127.0.0.1", 0) as (host, port):
        pass
    with pytest.raises(httpx.ConnectError):
        httpx.get(f"http://{host}:{port}/hello", trust_env=False)


def test_the_server_does_not_say_what_it_runs():
    with serving(app(), "127.0.0.1", 0) as (host, port):
        response = httpx.get(f"http://{host}:{port}/hello", trust_env=False)
    assert "server" not in response.headers


def test_a_port_in_use_is_an_os_error():
    with socket.create_server(("127.0.0.1", 0)) as busy:
        port = busy.getsockname()[1]
        with pytest.raises(OSError):
            with serving(app(), "127.0.0.1", port):
                pass
