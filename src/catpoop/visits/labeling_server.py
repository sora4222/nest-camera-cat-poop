"""Serve the labeling page with the standard library's HTTP server, on this machine only."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from catpoop.visits.labeling_app import LabelingApp

LOCALHOST = "127.0.0.1"


def make_server(app: LabelingApp, port: int = 8765) -> ThreadingHTTPServer:
    """An HTTP server for `app` bound to localhost; `port` 0 picks a free one."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._answer()

        def do_POST(self) -> None:
            self._answer()

        def _answer(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            response = app.handle(self.command, self.path, body, self.headers.get("Host", ""))
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(response.body)

        def log_message(self, format: str, *args: object) -> None:
            pass  # one line per frame is too much

    return ThreadingHTTPServer((LOCALHOST, port), Handler)
