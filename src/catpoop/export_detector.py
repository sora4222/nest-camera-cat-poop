"""Export a TensorFlow detector (TF2 model zoo SavedModel) to ONNX with tf2onnx.

Needs the `train` extra. `make export-detector OUT=...` runs it; by default it downloads
SSD MobileNet v2 FPNLite 320 (COCO, Apache-2.0) from the TF2 Object Detection model zoo.
The exported model keeps its post-processing, so the "onnx" detector can run it as is.
"""

import argparse
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

DEFAULT_URL = (
    "https://download.tensorflow.org/models/object_detection/tf2/20200711/"
    "ssd_mobilenet_v2_fpnlite_320x320_coco17_tpu-8.tar.gz"
)
OPSET = 17


def unpack(archive: Path, into: Path) -> Path:
    """Extract the tarball `archive` into `into` and return `into`."""
    into.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tar:
        tar.extractall(into, filter="data")
    return into


def find_saved_model(folder: Path) -> Path:
    """The folder under `folder` that holds `saved_model.pb`."""
    for found in sorted(folder.rglob("saved_model.pb")):
        return found.parent
    raise FileNotFoundError(f"no saved_model.pb under {folder}")


def tf2onnx_command(saved_model: Path, output: Path, opset: int = OPSET) -> list[str]:
    """The tf2onnx command line that converts `saved_model` to `output`."""
    return [
        sys.executable,
        "-m",
        "tf2onnx.convert",
        "--saved-model",
        str(saved_model),
        "--opset",
        str(opset),
        "--output",
        str(output),
    ]


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main(argv: list[str] | None = None) -> int:
    """Download or unpack the detector if needed, then convert it to ONNX."""
    parser = argparse.ArgumentParser(prog="python -m catpoop.export_detector")
    parser.add_argument("--output", type=Path, required=True, help="the .onnx file to write")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--saved-model", type=Path, help="an exported SavedModel folder")
    source.add_argument("--archive", type=Path, help="a model zoo .tar.gz already downloaded")
    source.add_argument("--url", default=DEFAULT_URL, help="a model zoo .tar.gz to download")
    parser.add_argument("--opset", type=int, default=OPSET)
    args = parser.parse_args(argv)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        saved_model = args.saved_model
        if saved_model is None:
            archive = args.archive
            if archive is None:
                archive = Path(temp) / "model.tar.gz"
                print(f"Downloading {args.url}")
                urllib.request.urlretrieve(args.url, archive)
            saved_model = find_saved_model(unpack(archive, Path(temp) / "model"))
        _run(tf2onnx_command(saved_model, args.output, args.opset))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
