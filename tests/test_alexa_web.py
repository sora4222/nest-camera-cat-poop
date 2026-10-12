import json

import httpx
import pytest

from catpoop.alexa_web import AlexaWeb, AlexaWebError

TOKEN = "Atnr|secret-refresh-token"
DEVICES = [
    {
        "accountName": "Kitchen",
        "serialNumber": "SERIAL1",
        "deviceType": "TYPE1",
        "deviceOwnerCustomerId": "CUSTOMER1",
    }
]


class Amazon:
    """A fake of the Amazon login and Alexa web endpoints."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.logins = 0
        self.speak_status = [200]

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/ap/exchangetoken/cookies":
            self.logins += 1
            cookies = [{"Name": "session-id", "Value": f"s{self.logins}"}]
            cookies.append({"Name": "csrf", "Value": f"c{self.logins}"})
            return httpx.Response(
                200, json={"response": {"tokens": {"cookies": {".amazon.com.au": cookies}}}}
            )
        if path == "/api/devices-v2/device":
            return httpx.Response(200, json={"devices": DEVICES})
        if path == "/api/behaviors/preview":
            return httpx.Response(self.speak_status.pop(0) if self.speak_status else 200)
        return httpx.Response(404)


def web(fake: Amazon) -> AlexaWeb:
    http = httpx.Client(transport=httpx.MockTransport(fake.handle))
    return AlexaWeb(TOKEN, domain="amazon.com.au", locale="en-AU", http=http)


def test_speak_logs_in_with_the_refresh_token_then_speaks_on_the_named_device():
    fake = Amazon()
    web(fake).speak("Kitchen", "Poop in the litter box")
    login, devices, speak = fake.requests
    assert str(login.url) == "https://api.amazon.com.au/ap/exchangetoken/cookies"
    assert f"source_token={TOKEN}".replace("|", "%7C") in login.content.decode()
    assert devices.url.host == "alexa.amazon.com.au"
    assert speak.headers["csrf"] == "c1"
    assert "session-id=s1" in speak.headers["cookie"]
    sequence = json.loads(json.loads(speak.content)["sequenceJson"])
    payload = sequence["startNode"]["operationPayload"]
    assert sequence["startNode"]["type"] == "Alexa.Speak"
    assert payload == {
        "deviceType": "TYPE1",
        "deviceSerialNumber": "SERIAL1",
        "customerId": "CUSTOMER1",
        "locale": "en-AU",
        "textToSpeak": "Poop in the litter box",
    }


def test_second_speak_reuses_the_login_and_device_list():
    fake = Amazon()
    alexa = web(fake)
    alexa.speak("Kitchen", "one")
    alexa.speak("Kitchen", "two")
    assert fake.logins == 1
    assert len(fake.requests) == 4


def test_expired_login_logs_in_again_once():
    fake = Amazon()
    alexa = web(fake)
    alexa.speak("Kitchen", "one")
    fake.speak_status = [401, 200]
    alexa.speak("Kitchen", "two")
    assert fake.logins == 2
    assert fake.requests[-1].headers["csrf"] == "c2"


def test_refused_twice_raises():
    fake = Amazon()
    fake.speak_status = [401, 401]
    with pytest.raises(AlexaWebError, match="401"):
        web(fake).speak("Kitchen", "hi")


def test_unknown_device_names_the_known_ones():
    with pytest.raises(AlexaWebError, match="Kitchen"):
        web(Amazon()).speak("Bedroom", "hi")


def test_network_failure_raises_without_the_token():
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot connect {request.content.decode()}")

    alexa = AlexaWeb(TOKEN, http=httpx.Client(transport=httpx.MockTransport(fail)))
    with pytest.raises(AlexaWebError) as error:
        alexa.speak("Kitchen", "hi")
    assert "secret" not in str(error.value)
    assert error.value.__cause__ is None


def test_token_is_not_in_repr():
    assert "secret" not in repr(web(Amazon()))
