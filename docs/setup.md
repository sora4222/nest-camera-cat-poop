# Setup

## Install

Needs [uv](https://docs.astral.sh/uv/) and Linux or macOS.

```sh
make setup      # installs the package and dev tools, creates config.toml and .env
```

The detector runs on ONNX Runtime from one of the `cpu` (default), `amd` or `nvidia` extras; pick one with `make dev RUNTIME=nvidia` and use the same `RUNTIME` for other Make targets. Only one can be installed at a time. Add `--extra train` on the machine that trains models (see [ADR 0002](adr/0002-train-in-tensorflow-run-with-onnx-runtime.md)).

## Pet detector

The "onnx" detector runs a TensorFlow Object Detection API model exported to ONNX. Make one on a machine with the `train` extra:

```sh
make export-detector OUT=/mnt/nas/cat-poop/models/pets.onnx   # downloads SSD MobileNet v2 FPNLite 320
make export-detector OUT=... SAVED_MODEL=path/to/saved_model    # or convert another TF2 zoo model
```

Then set `[detector] model` in `config.toml`. To try another detector, export it and change `model` (and `labels` if its class ids differ).

## Private files

Neither file is ever committed. Both are listed in `.worktreeinclude`, so Claude Code copies them into new worktrees.

- `config.toml`: names, Listeners, Speakers, Message templates, Quiet Hours, timers and the Private Data Store path. Copied from `config.example.toml`. Another file can be used with `CATPOOP_CONFIG=/path/to/config.toml`. See [configuration.md](configuration.md).
- `.env`: secrets. Copied from `.env.example`. Use 1Password references (`op://vault/item/field`) where possible; with the 1Password CLI (`op`) installed, Make targets run through `op run` to fill them in.

Check the config with `make config`.

## Camera login

The camera package is [googlenestcam](https://github.com/sora4222/nest-camera-access-python). Follow its login guide once; keep the Token file outside the repo and point `GOOGLENESTCAM_TOKEN_PATH` in `.env` at it.

## One watcher per machine

The live watcher takes a lock at `paths.lock_file` (default `/tmp/catpoop-watcher.lock`). Every worktree on a machine uses the same path, so a second watcher refuses to start. The lock is dropped when the process ends.
