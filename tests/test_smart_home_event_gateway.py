import json
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest
from fake_clock import FakeClock

from catpoop.alexa_smart_home.event_gateway import EventGateway, GatewayError

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class Tokens:
    def access_token(self) -> str:
        return "tok"


CLOCK = FakeClock(NOW)


class Later:
    def __init__(self) -> None:
        self.waiting: list[tuple[float, Callable[[], None]]] = []

    def __call__(self, seconds: float, action) -> None:
        self.waiting.append((seconds, action))

    def run(self) -> None:
        for seconds, action in self.waiting:
            CLOCK.advance(seconds)
            action()


def gateway(handler, region="FE", later=None) -> EventGateway:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return EventGateway(Tokens(), region, CLOCK, http, later or Later())


def test_trigger_reports_motion_now_and_rest_30_seconds_later():
    sent: list[httpx.Request] = []

    def accept(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(202)

    later = Later()
    gateway(accept, later=later).trigger("catpoop-poop")
    assert len(sent) == 1
    assert [seconds for seconds, _ in later.waiting] == [30.0]
    later.run()
    assert [str(r.url) for r in sent] == ["https://api.fe.amazonalexa.com/v3/events"] * 2
    first, second = (json.loads(r.content) for r in sent)
    assert first["event"]["header"]["name"] == "ChangeReport"
    assert first["event"]["endpoint"] == {
        "scope": {"type": "BearerToken", "token": "tok"},
        "endpointId": "catpoop-poop",
    }
    states = [b["event"]["payload"]["change"]["properties"][0]["value"] for b in (first, second)]
    assert states == ["DETECTED", "NOT_DETECTED"]
    times = [
        b["event"]["payload"]["change"]["properties"][0]["timeOfSample"] for b in (first, second)
    ]
    assert times[0] != times[1]
    assert sent[0].headers["authorization"] == "Bearer tok"


def test_refused_report_raises():
    with pytest.raises(GatewayError, match="403"):
        gateway(lambda r: httpx.Response(403)).trigger("catpoop-poop")


def test_network_failure_raises_without_the_token():
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(request.headers["authorization"])

    with pytest.raises(GatewayError) as error:
        gateway(fail).trigger("catpoop-poop")
    assert "tok" not in str(error.value)


def test_a_failed_reset_is_only_logged(caplog):
    replies = iter([httpx.Response(202), httpx.Response(500)])
    later = Later()
    gateway(lambda r: next(replies), later=later).trigger("catpoop-poop")
    later.run()
    assert "back to rest" in caplog.text
