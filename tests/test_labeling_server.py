import json
import threading

import httpx

from catpoop.visits.labeling_app import LabelingApp
from catpoop.visits.labeling_server import make_server
from catpoop.visits.store import VisitStore


def test_serves_the_app_on_localhost(tmp_path):
    server = make_server(LabelingApp(VisitStore(tmp_path)), port=0)
    host, port = server.server_address[:2]
    assert host == "127.0.0.1"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
            assert json.loads(client.get("/api/next").content) == {"visit": None, "remaining": 0}
            assert client.post("/api/label", content=b"{}").status_code == 400
            assert client.get("/").headers["content-type"].startswith("text/html")
    finally:
        server.shutdown()
        server.server_close()
