"""The labeling page's requests and answers, without any web server.

`GET /` is the page, `GET /api/next` the oldest unlabeled Visit, `GET /frames/<id>/<n>.jpg`
its frames, and `POST /api/label` with `{"visit_id", "outcome"}` gives a Visit its Outcome.
Only requests addressed to this machine (`localhost`, `127.0.0.1`) are answered.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources

from catpoop.domain import Outcome
from catpoop.visits.store import VisitStore

_FRAME = re.compile(r"^/frames/([^/]+)/(\d+)\.jpg$")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]"}


@dataclass(frozen=True)
class Response:
    """What to send back."""

    status: int
    content_type: str
    body: bytes


def _json(data: object, status: int = 200) -> Response:
    return Response(status, "application/json", json.dumps(data).encode())


def _error(status: int, message: str) -> Response:
    return _json({"error": message}, status)


class LabelingApp:
    """Shows unlabeled Visits one at a time and saves the Outcome chosen for each."""

    def __init__(
        self, store: VisitStore, now: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        """Label the Visits in `store`."""
        self._store = store
        self._now = now
        self._page = resources.files("catpoop.visits").joinpath("labeling.html").read_bytes()

    def handle(self, method: str, path: str, body: bytes, host: str) -> Response:
        """Answer one request. `host` is the request's Host header."""
        if re.sub(r":\d+$", "", host) not in _LOCAL_HOSTS:
            return _error(403, "only requests to localhost are answered")
        path = path.split("?", 1)[0]
        if method == "GET" and path == "/":
            return Response(200, "text/html; charset=utf-8", self._page)
        if method == "GET" and path == "/api/next":
            return self._next()
        if method == "GET" and (match := _FRAME.match(path)):
            return self._frame(match[1], int(match[2]))
        if method == "POST" and path == "/api/label":
            return self._label(body)
        return _error(404, "not found")

    def _next(self) -> Response:
        waiting = self._store.unlabeled()
        if not waiting:
            return _json({"visit": None, "remaining": 0})
        visit = waiting[0]
        return _json(
            {
                "visit": {
                    "id": visit.id,
                    "frames": visit.frames,
                    "start": visit.start,
                    "end": visit.end,
                    "recorded_at": visit.recorded_at,
                },
                "remaining": len(waiting),
            }
        )

    def _frame(self, id: str, number: int) -> Response:
        path = self._store.frame_path(id, number)
        if path is None or not path.exists():
            return _error(404, "no such frame")
        return Response(200, "image/jpeg", path.read_bytes())

    def _label(self, body: bytes) -> Response:
        try:
            request = json.loads(body)
            id, outcome = str(request["visit_id"]), Outcome(request["outcome"])
        except (ValueError, KeyError, TypeError):
            return _error(400, "send {visit_id, outcome} with outcome pee, poop or nothing")
        try:
            visit = self._store.label(id, outcome, self._now())
        except KeyError:
            return _error(404, "no such Visit")
        return _json({"visit_id": visit.id, "outcome": outcome.value})
