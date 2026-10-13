import numpy as np
import pytest

pytest.importorskip("tensorflow")
pytest.importorskip("tf2onnx")
ort = pytest.importorskip("onnxruntime")
from catpoop.outcome.network import build_model  # noqa: E402
from catpoop.outcome.onnx_export import export_onnx  # noqa: E402

SIZE = 32


def inputs(with_time):
    rng = np.random.default_rng(1)
    feed = {"image": rng.uniform(0, 255, (2, SIZE, SIZE, 3)).astype(np.float32)}
    if with_time:
        feed["time"] = rng.uniform(-1, 1, (2, 3)).astype(np.float32)
    return feed


@pytest.mark.parametrize("with_time", [False, True])
def test_small_model_gives_three_scores(with_time):
    model = build_model(SIZE, "small", with_time)
    scores = model.predict(inputs(with_time), verbose=0)
    assert scores.shape == (2, 3)
    assert scores.sum(axis=1) == pytest.approx([1.0, 1.0], abs=1e-5)


@pytest.mark.parametrize("with_time", [False, True])
def test_onnx_export_gives_the_same_scores(tmp_path, with_time):
    model = build_model(SIZE, "small", with_time)
    path = tmp_path / "model.onnx"
    export_onnx(model, path, SIZE, with_time)
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    assert sorted(i.name for i in session.get_inputs()) == sorted(inputs(with_time))
    [scores] = session.run(["scores"], inputs(with_time))
    assert scores == pytest.approx(model.predict(inputs(with_time), verbose=0), abs=1e-5)


def test_unknown_backbone_is_an_error():
    with pytest.raises(ValueError, match="backbone"):
        build_model(SIZE, "huge", False)
