"""Serve spoken wav clips over HTTP on the home network, so a Google speaker can fetch them.

Each clip gets a random, unguessable URL and is forgotten after `keep_seconds`. The server
starts on the first offer, in a background thread, bound to one LAN address only.
"""

import secrets
import socket
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from catpoop.clock import Clock, SystemClock


def lan_address() -> str:
    """This machine's address on the network that leads to the internet (no packet is sent)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect(("8.8.8.8", 80))  # public unicast: takes the default route
        return probe.getsockname()[0]


class AudioServer:
    """Hands out a URL for each wav clip and serves it for a while."""

    def __init__(
        self, host: str, port: int = 8766, keep_seconds: float = 120, clock: Clock | None = None
    ) -> None:
        """Serve on `host`:`port` (`port` 0 picks a free one); nothing listens until `offer`."""
        self._host = host
        self._port = port
        self._keep = timedelta(seconds=keep_seconds)
        self._clock = clock or SystemClock()
        self._lock = threading.Lock()
        self._clips: dict[str, tuple[bytes, datetime]] = {}
        self._server: ThreadingHTTPServer | None = None
        self._server_lock = threading.Lock()
        """Held while starting or stopping, so Speakers on their own threads start one server."""

    def offer(self, wav: bytes) -> str:
        """Keep `wav` for `keep_seconds` and give the URL it is served at."""
        now = self._clock.now()
        name = f"{secrets.token_urlsafe(16)}.wav"
        with self._lock:
            self._clips = {k: v for k, v in self._clips.items() if now - v[1] < self._keep}
            self._clips[name] = (wav, now)
        server = self._start()
        host, port = server.server_address[:2]
        return f"http://{host}:{port}/{name}"

    def close(self) -> None:
        """Stop serving."""
        with self._server_lock:
            server, self._server = self._server, None
        if server is not None:
            server.shutdown()
            server.server_close()

    def _clip(self, name: str) -> bytes | None:
        with self._lock:
            found = self._clips.get(name)
        if found is None or self._clock.now() - found[1] >= self._keep:
            return None
        return found[0]

    def _start(self) -> ThreadingHTTPServer:
        with self._server_lock:
            if self._server is None:
                self._server = ThreadingHTTPServer((self._host, self._port), self._handler())
                threading.Thread(
                    target=self._server.serve_forever, name="audio-server", daemon=True
                ).start()
            return self._server

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        clip = self._clip

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                wav = clip(self.path.lstrip("/"))
                if wav is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(wav)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(wav)

            def log_message(self, format: str, *args: object) -> None:
                pass

        return Handler
