"""Serve the Alexa endpoint with the standard library's HTTP server.

It listens on this machine only by default (`127.0.0.1`); the tunnel (Cloudflare or
Tailscale) brings `/alexa` from the internet to it.
"""

import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol

from catpoop.alexa_skill.endpoint import MAX_BODY, EndpointResponse

log = logging.getLogger(__name__)


class Endpoint(Protocol):
    """Answers one HTTP request (`AlexaEndpoint`)."""

    def handle(
        self, method: str, path: str, headers: dict[str, str], body: bytes
    ) -> EndpointResponse:
        """The response."""
        ...


def make_server(endpoint: Endpoint, host: str, port: int) -> ThreadingHTTPServer:
    """An HTTP server for `endpoint` on `host:port`; port 0 picks a free one.

    Requests are read on their own threads, but `endpoint` answers one at a time, so two
    intents never change the switches together.
    """
    one_at_a_time = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "catpoop"
        sys_version = ""
        timeout = 10

        def __getattr__(self, name: str) -> Any:
            if name.startswith("do_"):  # every method (GET, PATCH, ...) goes to the endpoint
                return self._answer
            raise AttributeError(name)

        def _answer(self) -> None:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length < 0 or length > MAX_BODY:
                self._send(EndpointResponse(413, b"too large"))
                self.close_connection = True
                return
            body = self.rfile.read(length) if length else b""
            with one_at_a_time:
                response = endpoint.handle(self.command, self.path, dict(self.headers), body)
            self._send(response)

        def _send(self, response: EndpointResponse) -> None:
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(response.body)

        def log_message(self, format: str, *args: object) -> None:
            log.debug(format, *args)

    return ThreadingHTTPServer((host, port), Handler)
