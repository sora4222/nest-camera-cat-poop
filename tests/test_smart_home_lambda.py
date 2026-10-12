import importlib.util
import io
import json
from pathlib import Path

LAMBDA = Path(__file__).parent.parent / "alexa" / "smart_home_lambda.py"


def load():
    spec = importlib.util.spec_from_file_location("smart_home_lambda", LAMBDA)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_forwards_the_directive_with_the_secret_and_returns_the_answer(monkeypatch):
    module = load()
    seen = []

    def urlopen(request, timeout):
        seen.append(request)
        return io.BytesIO(b'{"event": "ok"}')

    monkeypatch.setattr(module.urllib.request, "urlopen", urlopen)
    monkeypatch.setenv("CATPOOP_URL", "https://litter.example.com/alexa/smart-home")
    monkeypatch.setenv("CATPOOP_SECRET", "s3cret")
    answer = module.lambda_handler({"directive": {}}, None)
    assert answer == {"event": "ok"}
    [request] = seen
    assert request.full_url == "https://litter.example.com/alexa/smart-home"
    assert request.get_header("Authorization") == "Bearer s3cret"
    assert json.loads(request.data) == {"directive": {}}
