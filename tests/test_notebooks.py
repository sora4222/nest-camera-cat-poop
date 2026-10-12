from pathlib import Path

import pytest

NOTEBOOKS = Path(__file__).parent.parent / "notebooks"


@pytest.mark.parametrize("name", ["export_toy_model_to_onnx.ipynb"])
def test_notebook_runs_top_to_bottom(name, tmp_path):
    for module in ["tensorflow", "tf2onnx", "onnxruntime", "ipykernel"]:
        pytest.importorskip(module)
    nbclient = pytest.importorskip("nbclient")
    nbformat = pytest.importorskip("nbformat")

    notebook = nbformat.read(NOTEBOOKS / name, as_version=4)
    client = nbclient.NotebookClient(
        notebook, timeout=600, kernel_name="python3", resources={"metadata": {"path": tmp_path}}
    )
    client.execute()
