import json
from datetime import UTC, datetime

import httpx
import pytest
from fake_clock import FakeClock

from catpoop.alexa_smart_home.event_gateway import EventGateway, GatewayError

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class Tokens:
    def access_token(self) -> str:
        return "tok"


def gateway(handler, region="FE") -> EventGateway:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return EventGateway(Tokens(), region, FakeClock(NOW), http)


def test_trigger_reports_motion_then_rest_to_the_region():
    sent: list[httpx.Request] = []

    def accept(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(202)

    gateway(accept).trigger("catpoop-poop")
    assert [str(r.url) for r in sent] == ["https://api.fe.amazonalexa.com/v3/events"] * 2
    first, second = (json.loads(r.content) for r in sent)
    assert first["event"]["header"]["name"] == "ChangeReport"
    assert first["event"]["endpoint"] == {
        "scope": {"type": "BearerToken", "token": "tok"},
        "endpointId": "catpoop-poop",
    }
    states = [b["event"]["payload"]["change"]["properties"][0]["value"] for b in (first, second)]
    assert states == ["DETECTED", "NOT_DETECTED"]
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
