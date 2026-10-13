# Setup

## Install

Needs [uv](https://docs.astral.sh/uv/) and Linux or macOS.

```sh
make setup      # installs dependencies, creates config.toml and .env
```

The detector runs on ONNX Runtime from one of the `cpu` (default), `amd` or `nvidia` extras; pick one with `make setup RUNTIME=nvidia` and use the same `RUNTIME` for other Make targets. Only one can be installed at a time. Google speakers need `make setup EXTRAS=google`, which only works with `RUNTIME=cpu` (Piper brings the CPU ONNX Runtime); use the same `EXTRAS` for other Make targets. Add `--extra train` on the machine that trains models (see [ADR 0002](adr/0002-train-in-tensorflow-run-with-onnx-runtime.md)).

## Pet detector

The "onnx" detector runs a TensorFlow Object Detection API model exported to ONNX. Make one on a machine with the `train` extra:

```sh
make export-detector OUT=/mnt/nas/cat-poop/models/pets.onnx   # downloads SSD MobileNet v2 FPNLite 320
make export-detector OUT=... SAVED_MODEL=path/to/saved_model    # or convert another TF2 zoo model
```

Then set `[detector] model` in `config.toml`. To try another detector, export it and change `model` (and `labels` if its class ids differ).

New to ONNX? [notebooks/export_toy_model_to_onnx.ipynb](../notebooks/export_toy_model_to_onnx.ipynb) walks through the same steps on a tiny Keras model: export, look at the inputs and outputs, and check ONNX Runtime gives the same answers. Open it with `make notebook`.

## Private files

Neither file is ever committed. Both are listed in `.worktreeinclude`, so Claude Code copies them into new worktrees.

- `config.toml`: names, Listeners, Speakers, Message templates, Quiet Hours, timers and the Private Data Store path. Copied from `config.example.toml`. Another file can be used with `CATPOOP_CONFIG=/path/to/config.toml`. See [configuration.md](configuration.md).
- `.env`: secrets. Copied from `.env.example`. Use 1Password references (`op://vault/item/field`) where possible; with the 1Password CLI (`op`) installed, Make targets run through `op run` to fill them in.

The event log is PostgreSQL: `make db` starts it in Docker (needs Docker with Compose) and keeps it running across restarts, or point `CATPOOP_DATABASE_URL` in .env at your own. Check the config with `make config`. Run the live watcher with `make dev` (see [CONTRIBUTE.md](../CONTRIBUTE.md#running-the-live-watcher)); on the server, `make install` runs it as a service (see [service.md](service.md)).

## Camera login

The camera package is [googlenestcam](https://github.com/sora4222/nest-camera-access-python). Follow its login guide once; keep the Token file outside the repo and point `GOOGLENESTCAM_TOKEN_PATH` in `.env` at it.

## One watcher per machine

The live watcher takes a lock at `paths.lock_file` (default `$XDG_RUNTIME_DIR/catpoop-watcher.lock`, else `/tmp/catpoop-<uid>/watcher.lock`). Every worktree of the same user uses the same path, so a second watcher refuses to start. The lock is dropped when the process ends. The lock's folder must be owned by you and not writable by others, and the lock file is never opened through a symlink.
