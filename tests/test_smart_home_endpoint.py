from fastapi import FastAPI
from fastapi.testclient import TestClient

from catpoop.alexa_smart_home.endpoint import PATH, router

SECRET = {"authorization": "Bearer s3cret"}


class Skill:
    def answer(self, request: dict) -> dict:
        return {"echo": request}


def client(skill: object | None = None) -> TestClient:
    app = FastAPI()
    app.state.smart_home_secret, app.state.smart_home = "s3cret", skill or Skill()
    app.include_router(router)
    return TestClient(app)


def test_with_the_secret_the_skill_answers():
    answer = client().post(PATH, content=b'{"a": 1}', headers=SECRET)
    assert answer.status_code == 200
    assert answer.json() == {"echo": {"a": 1}}


def test_without_the_secret_it_is_401():
    assert client().post(PATH, content=b"{}").status_code == 401
    assert (
        client().post(PATH, content=b"{}", headers={"Authorization": "Bearer no"}).status_code
        == 401
    )


def test_other_methods_and_paths_are_refused():
    assert client().get(PATH, headers=SECRET).status_code == 405
    assert client().post("/x", headers=SECRET).status_code == 404


def test_a_failing_skill_is_500():
    class Broken:
        def answer(self, request: dict) -> dict:
            raise RuntimeError("boom")

    assert client(Broken()).post(PATH, content=b"{}", headers=SECRET).status_code == 500
