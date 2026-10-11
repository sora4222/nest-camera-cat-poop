# Training the Outcome model

Once some Visits are [labeled](visits.md), train the Outcome model and check how good it is:

```sh
make train      # train on dataset/, export to ONNX, print accuracy per class (needs the train extra)
make evaluate   # accuracy per class of the exported ONNX files, with ONNX Runtime only
```

`make train` installs TensorFlow (the `train` extra) on first use; train on a machine with enough memory. The always-on server only needs `make evaluate` and the ONNX files ([ADR 0002](adr/0002-train-in-tensorflow-run-with-onnx-runtime.md)).

## Two models

| Model | Learns from | Used for |
|---|---|---|
| `outcome.onnx` | the last frame of each Visit: the litter surface after the Cat has left | the Outcome |
| `outcome_guess.onnx` | `guess_frames_per_visit` frames from the middle of each Visit (the Cat's stance) and the time of day | the Outcome Guess while the Visit is still going |

Both give one score per Outcome (Pee, Poop, Nothing). Rare Outcomes are weighted up so they count as much as common ones. Each Visit is held out for validation or not by its id (about `validation_fraction` of them), so the split never changes and a Visit is never on both sides. The time of day is read in this machine's time zone; Visits with no recorded time are trained on without it and left out of the Outcome Guess accuracy.

The picture network is `backbone = "mobilenet"` (MobileNetV3 Small pretrained on ImageNet, frozen; the weights are downloaded once from Google) or `"small"` (a tiny network learned from scratch). Settings are in `[outcome]` in `config.toml`.

## What is stored

Under `paths.private_data_store`, in `outcome.models` (default `models/outcome/`):

- `outcome.onnx`: input `image` `[N, S, S, 3]` float32 RGB pixels 0-255, output `scores` `[N, 3]`.
- `outcome_guess.onnx`: inputs `image` and `time` `[N, 3]` (`sin` and `cos` of the time of day, and 1 if it is known), output `scores`.
- `outcome.json`: the picture size `S` and the Outcome of each score.

The old files are only replaced once both new models are exported.

## On the server

`catpoop.outcome.onnx_outcome.load_outcome_model` opens the files with ONNX Runtime on `outcome.runtime` (auto, cpu, amd or nvidia) and gives an `OutcomeModel` (`src/catpoop/interfaces.py`): `outcome(frame)` and `guess(frame)` each return `OutcomeScores`. Pictures are resized with the same code in training and on the server.
