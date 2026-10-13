from datetime import UTC, datetime

from fake_clock import FakeClock

from catpoop.alexa_smart_home.directives import SmartHome
from catpoop.alexa_smart_home.sensors import Sensor

NOW = datetime(2026, 1, 1, 8, 30, tzinfo=UTC)
POOP = Sensor("poop", "catpoop-poop", "Litter box poop")


class Grant:
    def __init__(self, fail: bool = False) -> None:
        self.codes: list[str] = []
        self.fail = fail

    def accept(self, code: str) -> None:
        if self.fail:
            raise RuntimeError("refused")
        self.codes.append(code)


def directive(namespace: str, name: str, **extra) -> dict:
    header = {"namespace": namespace, "name": name, "messageId": "m", "payloadVersion": "3"}
    return {"directive": {"header": header, **extra}}


def home(grant: Grant | None = None) -> SmartHome:
    return SmartHome([POOP], grant or Grant(), FakeClock(NOW))


def test_discovery_lists_a_motion_sensor_per_message():
    answer = home().answer(directive("Alexa.Discovery", "Discover", payload={}))
    assert answer["event"]["header"]["name"] == "Discover.Response"
    [endpoint] = answer["event"]["payload"]["endpoints"]
    assert endpoint["endpointId"] == "catpoop-poop"
    assert endpoint["friendlyName"] == "Litter box poop"
    assert endpoint["displayCategories"] == ["MOTION_SENSOR"]
    motion = endpoint["capabilities"][0]
    assert motion["interface"] == "Alexa.MotionSensor"
    assert motion["properties"]["proactivelyReported"] is True
    health = endpoint["capabilities"][1]
    assert (health["interface"], health["version"]) == ("Alexa.EndpointHealth", "3.1")
    assert health["properties"]["proactivelyReported"] is True


def test_accept_grant_hands_the_code_over():
    grant = Grant()
    payload = {"grant": {"type": "OAuth2.AuthorizationCode", "code": "abc"}, "grantee": {}}
    answer = home(grant).answer(directive("Alexa.Authorization", "AcceptGrant", payload=payload))
    assert answer["event"]["header"]["name"] == "AcceptGrant.Response"
    assert grant.codes == ["abc"]


def test_failed_grant_is_an_accept_grant_error():
    payload = {"grant": {"code": "abc"}}
    answer = home(Grant(fail=True)).answer(
        directive("Alexa.Authorization", "AcceptGrant", payload=payload)
    )
    assert answer["event"]["payload"]["type"] == "ACCEPT_GRANT_FAILED"


def test_report_state_is_not_detected():
    header = {"namespace": "Alexa", "name": "ReportState", "correlationToken": "t"}
    request = {"directive": {"header": header, "endpoint": {"endpointId": "catpoop-poop"}}}
    answer = home().answer(request)
    assert answer["event"]["header"]["name"] == "StateReport"
    assert answer["event"]["header"]["correlationToken"] == "t"
    motion = answer["context"]["properties"][0]
    assert motion["value"] == "NOT_DETECTED"
    assert motion["timeOfSample"] == "2026-01-01T08:30:00.00Z"


def test_anything_else_is_invalid():
    answer = home().answer(directive("Alexa.PowerController", "TurnOn"))
    assert answer["event"]["payload"]["type"] == "INVALID_DIRECTIVE"
