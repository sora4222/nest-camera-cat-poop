# Train in TensorFlow, run with ONNX Runtime

Models (the ready-made pet detector and the Outcome model) are trained or fine-tuned in TensorFlow, then exported to ONNX and run on the server with ONNX Runtime. This keeps the always-on server install small and CPU-only by default. AMD (ROCm) and NVIDIA (CUDA) support are optional extras (`amd`, `nvidia`), and TensorFlow is only installed with the `train` extra on the machine that trains.

## Considered Options

- **TensorFlow on the server too**: much larger install, and AMD GPU support is weak.
- **PyTorch for training**: TensorFlow was preferred, to experiment with its detectors.
- **Ultralytics YOLO detector**: its AGPL licence does not sit well with this public-domain (Unlicense) repo, so an Apache-licensed TensorFlow detector is used.
