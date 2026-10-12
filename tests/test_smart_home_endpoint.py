import json

from catpoop.alexa_skill.endpoint import EndpointResponse
from catpoop.alexa_skill.routes import Routes
from catpoop.alexa_smart_home.endpoint import PATH, SmartHomeEndpoint


class Skill:
    def answer(self, request: dict) -> dict:
        return {"echo": request}


def endpoint() -> SmartHomeEndpoint:
    return SmartHomeEndpoint("s3cret", Skill())


def test_with_the_secret_the_skill_answers():
    answer = endpoint().handle("POST", PATH, {"authorization": "Bearer s3cret"}, b'{"a": 1}')
    assert answer.status == 200
    assert json.loads(answer.body) == {"echo": {"a": 1}}


def test_without_the_secret_it_is_401():
    assert endpoint().handle("POST", PATH, {}, b"{}").status == 401
    assert endpoint().handle("POST", PATH, {"Authorization": "Bearer no"}, b"{}").status == 401


def test_other_methods_and_paths_are_refused():
    assert endpoint().handle("GET", PATH, {"authorization": "Bearer s3cret"}, b"").status == 405
    assert endpoint().handle("POST", "/x", {}, b"").status == 404


def test_secret_is_not_in_repr():
    assert "s3cret" not in repr(endpoint())


class Fixed:
    def handle(self, method, path, headers, body) -> EndpointResponse:
        return EndpointResponse(200, path.encode())


def test_routes_send_each_path_to_its_endpoint():
    routes = Routes({"/a": Fixed(), "/b": Fixed()})
    assert routes.handle("POST", "/b", {}, b"").body == b"/b"
    assert routes.handle("POST", "/c", {}, b"").status == 404
