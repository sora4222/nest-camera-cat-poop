import pytest

from catpoop.onnx_session import pick_providers

AVAILABLE = [
    "CUDAExecutionProvider",
    "MIGraphXExecutionProvider",
    "CPUExecutionProvider",
]


def test_cpu_uses_only_the_cpu():
    assert pick_providers("cpu", AVAILABLE) == ["CPUExecutionProvider"]


def test_nvidia_prefers_cuda_then_cpu():
    assert pick_providers("nvidia", AVAILABLE) == ["CUDAExecutionProvider", "CPUExecutionProvider"]


def test_amd_prefers_migraphx_then_cpu():
    assert pick_providers("amd", AVAILABLE) == [
        "MIGraphXExecutionProvider",
        "CPUExecutionProvider",
    ]


def test_auto_uses_any_gpu_that_is_installed():
    assert pick_providers("auto", ["ROCMExecutionProvider", "CPUExecutionProvider"]) == [
        "ROCMExecutionProvider",
        "CPUExecutionProvider",
    ]


def test_missing_gpu_falls_back_to_cpu():
    assert pick_providers("nvidia", ["CPUExecutionProvider"]) == ["CPUExecutionProvider"]


def test_unknown_runtime_is_an_error():
    with pytest.raises(ValueError, match="tpu"):
        pick_providers("tpu", AVAILABLE)
