"""Open an ONNX model with ONNX Runtime on the CPU or a GPU.

`onnxruntime` comes from the `cpu`, `amd` or `nvidia` extra and is imported only when a
model is opened, so the rest of the package works without it.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

_GPU_PROVIDERS = {
    "cpu": [],
    "nvidia": ["CUDAExecutionProvider"],
    "amd": ["MIGraphXExecutionProvider", "ROCMExecutionProvider"],
    "auto": ["CUDAExecutionProvider", "MIGraphXExecutionProvider", "ROCMExecutionProvider"],
}
RUNTIMES = tuple(_GPU_PROVIDERS)
"""Names accepted for `runtime`: cpu, nvidia, amd, or auto (any GPU that is installed)."""


def pick_providers(runtime: str, available: Sequence[str]) -> list[str]:
    """ONNX Runtime providers to try for `runtime`, best first, always ending with the CPU."""
    if runtime not in _GPU_PROVIDERS:
        raise ValueError(f"unknown runtime {runtime!r}; use one of {', '.join(RUNTIMES)}")
    gpus = [name for name in _GPU_PROVIDERS[runtime] if name in available]
    return [*gpus, "CPUExecutionProvider"]


def open_session(model: Path, runtime: str) -> Any:
    """An `onnxruntime.InferenceSession` for `model` on the providers `runtime` asks for."""
    import onnxruntime

    providers = pick_providers(runtime, onnxruntime.get_available_providers())
    return onnxruntime.InferenceSession(str(model), providers=providers)
