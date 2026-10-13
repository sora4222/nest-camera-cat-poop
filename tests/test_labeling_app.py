import json
from datetime import UTC, datetime

import numpy as np

from catpoop.domain import Outcome
from catpoop.visits.labeling_app import LabelingApp
from catpoop.visits.store import Visit, VisitStore, visit_id

NOW = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)
SHA = "ab" * 32
HOST = "127.0.0.1:8765"


def setup(tmp_path, starts=(1.0, 9.0)):
    store = VisitStore(tmp_path)
    frames = [np.zeros((4, 4, 3), np.uint8)] * 2
    for start in starts:
        store.add(Visit(visit_id(SHA, start), SHA, start, start + 3, None), frames)
    return store, LabelingApp(store, now=lambda: NOW)


def get_json(app, path):
    response = app.handle("GET", path, b"", HOST)
    assert response.status == 200
    return json.loads(response.body)


def label(app, id, outcome, host=HOST):
    body = json.dumps({"visit_id": id, "outcome": outcome}).encode()
    return app.handle("POST", "/api/label", body, host)


def test_page_has_the_three_outcomes(tmp_path):
    _, app = setup(tmp_path)
    response = app.handle("GET", "/", b"", HOST)
    assert response.status == 200
    assert response.content_type.startswith("text/html")
    for word in (b"Pee", b"Poop", b"Nothing"):
        assert word in response.body


def test_next_gives_the_oldest_unlabeled_visit(tmp_path):
    _, app = setup(tmp_path)
    answer = get_json(app, "/api/next")
    assert answer["remaining"] == 2
    assert answer["visit"]["id"] == visit_id(SHA, 1.0)
    assert answer["visit"]["frames"] == 2


def test_frames_are_served(tmp_path):
    _, app = setup(tmp_path)
    response = app.handle("GET", f"/frames/{visit_id(SHA, 1.0)}/2.jpg", b"", HOST)
    assert response.status == 200
    assert response.content_type == "image/jpeg"
    assert response.body[:2] == b"\xff\xd8"
    assert app.handle("GET", f"/frames/{visit_id(SHA, 1.0)}/3.jpg", b"", HOST).status == 404
    assert app.handle("GET", "/frames/../../etc/1.jpg", b"", HOST).status == 404


def test_labeling_moves_on_to_the_next_visit(tmp_path):
    store, app = setup(tmp_path)
    first = visit_id(SHA, 1.0)
    assert label(app, first, "poop").status == 200
    assert store.get(first).outcome is Outcome.POOP
    answer = get_json(app, "/api/next")
    assert (answer["remaining"], answer["visit"]["id"]) == (1, visit_id(SHA, 9.0))
    label(app, visit_id(SHA, 9.0), "nothing")
    assert get_json(app, "/api/next") == {"visit": None, "remaining": 0}


def test_bad_labels_are_refused(tmp_path):
    _, app = setup(tmp_path)
    assert label(app, visit_id(SHA, 1.0), "maybe").status == 400
    assert label(app, visit_id(SHA, 5.0), "pee").status == 404
    assert app.handle("POST", "/api/label", b"{", HOST).status == 400


def test_other_hosts_are_refused(tmp_path):
    _, app = setup(tmp_path)
    assert label(app, visit_id(SHA, 1.0), "pee", host="evil.example:8765").status == 403
    assert app.handle("GET", "/", b"", "evil.example").status == 403


def test_unknown_paths_are_not_found(tmp_path):
    _, app = setup(tmp_path)
    assert app.handle("GET", "/nope", b"", HOST).status == 404
    assert app.handle("DELETE", "/api/next", b"", HOST).status == 404


def test_a_visit_labeled_elsewhere_is_not_relabeled(tmp_path):
    store, app = setup(tmp_path)
    first = visit_id(SHA, 1.0)
    label(app, first, "poop")
    assert label(app, first, "pee").status == 409
    assert store.get(first).outcome is Outcome.POOP
