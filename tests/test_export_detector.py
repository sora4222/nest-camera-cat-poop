import io
import sys
import tarfile
from pathlib import Path

import pytest

from catpoop import export_detector
from catpoop.export_detector import find_saved_model, tf2onnx_command, unpack


def make_archive(path: Path) -> Path:
    """A tarball laid out like the TF2 model zoo: <name>/saved_model/saved_model.pb."""
    with tarfile.open(path, "w:gz") as tar:
        for name in ["ssd/pipeline.config", "ssd/saved_model/saved_model.pb"]:
            info = tarfile.TarInfo(name)
            info.size = 1
            tar.addfile(info, io.BytesIO(b"x"))
    return path


def test_unpacks_a_zoo_archive_and_finds_the_saved_model(tmp_path):
    folder = unpack(make_archive(tmp_path / "ssd.tar.gz"), tmp_path / "out")
    assert find_saved_model(folder) == tmp_path / "out" / "ssd" / "saved_model"


def test_no_saved_model_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError, match=r"saved_model\.pb"):
        find_saved_model(tmp_path)


def test_command_runs_tf2onnx_with_this_python(tmp_path):
    command = tf2onnx_command(tmp_path / "sm", tmp_path / "pets.onnx", opset=17)
    assert command[:3] == [sys.executable, "-m", "tf2onnx.convert"]
    assert command[3:] == [
        "--saved-model",
        str(tmp_path / "sm"),
        "--opset",
        "17",
        "--output",
        str(tmp_path / "pets.onnx"),
    ]


def test_main_converts_a_local_archive(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(export_detector, "_run", calls.append)
    archive = make_archive(tmp_path / "ssd.tar.gz")
    out = tmp_path / "models" / "pets.onnx"
    assert export_detector.main(["--archive", str(archive), "--output", str(out)]) == 0
    [command] = calls
    assert command[command.index("--output") + 1] == str(out)
    assert command[command.index("--saved-model") + 1].endswith("ssd/saved_model")
    assert out.parent.is_dir()


def test_main_converts_a_saved_model_folder(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(export_detector, "_run", calls.append)
    (tmp_path / "sm").mkdir()
    (tmp_path / "sm" / "saved_model.pb").write_bytes(b"x")
    out = tmp_path / "pets.onnx"
    assert export_detector.main(["--saved-model", str(tmp_path / "sm"), "--output", str(out)]) == 0
    assert calls[0][calls[0].index("--saved-model") + 1] == str(tmp_path / "sm")


def test_real_conversion_of_a_tiny_saved_model(tmp_path):
    tf = pytest.importorskip("tensorflow")
    pytest.importorskip("tf2onnx")

    class Double(tf.Module):
        @tf.function(input_signature=[tf.TensorSpec([1, None, None, 3], tf.uint8)])
        def __call__(self, image):
            return {"doubled": tf.cast(image, tf.float32) * 2.0}

    tf.saved_model.save(Double(), str(tmp_path / "sm"))
    out = tmp_path / "double.onnx"
    assert export_detector.main(["--saved-model", str(tmp_path / "sm"), "--output", str(out)]) == 0
    assert out.stat().st_size > 0
