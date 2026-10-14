.PHONY: help setup db migration dev check format test config import-history export-detector notebook cut-visits label add-visit train evaluate dnd dnd-off pee-on pee-off install uninstall alexa-tunnel

# ONNX Runtime for the detector: cpu (default), amd or nvidia. E.g. `make setup RUNTIME=nvidia`.
RUNTIME ?= cpu
# More extras, e.g. `make setup EXTRAS=google` for Google speakers (needs RUNTIME=cpu).
EXTRAS ?=
UV_EXTRAS := --extra $(RUNTIME) $(addprefix --extra ,$(EXTRAS))
UV_RUN := uv run $(UV_EXTRAS)

# Commands that need secrets run through $(RUN). With the 1Password CLI (`op`)
# installed, `op://` references in .env are filled in; otherwise .env is read as is.
ifneq ($(wildcard .env),)
  ifneq ($(shell command -v op 2>/dev/null),)
    RUN := op run --env-file=.env -- $(UV_RUN)
  else
    RUN := $(UV_RUN) --env-file .env
  endif
else
  RUN := $(UV_RUN)
endif

help:
	@echo "make setup   install dependencies (RUNTIME=cpu|amd|nvidia, EXTRAS=google), create config.toml and .env if missing"
	@echo "make db      start PostgreSQL in Docker (compose.yaml) for the event log and tests"
	@echo "make migration MSG=\"...\"  new empty Alembic migration in src/catpoop/migrations/versions"
	@echo "make dev     run the live watcher (Ctrl+C stops it)"
	@echo "make install    run the watcher from this checkout as a systemd user service (same RUNTIME, EXTRAS as setup)"
	@echo "make uninstall  stop and remove that service"
	@echo "make check   format check, lint and type check"
	@echo "make format  format and auto-fix lint"
	@echo "make test    run the tests"
	@echo "make config  load the private config and say if it is valid"
	@echo "make import-history ARGS=\"takeout|portability|folder [paths]\"  copy past clips to the NAS"
	@echo "make export-detector OUT=x.onnx [SAVED_MODEL=dir]  TF detector to ONNX (train extra)"
	@echo "make notebook  open JupyterLab on notebooks/ (train extra + notebook group)"
	@echo "make cut-visits  cut new clips into Visits; delete old unlabeled clips over the limit"
	@echo "make label [PORT=8765]  labeling page on http://localhost:PORT/"
	@echo "make add-visit OUTCOME=poop|pee|nothing CLIPS=\"a.mp4 b.mp4\"  clips found by hand to the dataset"
	@echo "make train     train the Outcome model on the dataset, export it to ONNX (train extra)"
	@echo "make evaluate  accuracy per class of the exported Outcome model on held-out Visits"
	@echo "make dnd FOR=2h [ALLOW=\"urgent\"]  Do Not Disturb for a while (ALLOW: Urgencies still spoken, or none)"
	@echo "make dnd-off   turn Do Not Disturb off"
	@echo "make pee-on / make pee-off  turn Pee announcements on or off"
	@echo "make alexa-tunnel  how to open only /alexa with the [alexa_skill] tunnel (cloudflare or tailscale)"

# Copy the example files only if the private ones do not exist yet.
setup:
	uv sync $(UV_EXTRAS)
	@test -f config.toml || { cp config.example.toml config.toml && echo "Created config.toml; edit it."; }
	@test -f .env || { cp .env.example .env && echo "Created .env; edit it."; }

# PostgreSQL in Docker, on this machine only. Tests use it when Docker is there.

db:
	docker compose up --detach --wait db

migration:
	@test -n "$(MSG)" || { echo "Set MSG, e.g. make migration MSG=\"add visits table\""; exit 1; }
	uv run alembic revision -m "$(MSG)"
	uv run ruff format src/catpoop/migrations

# Starts the Docker database only when .env points at it.
dev:
	@if grep -q '^CATPOOP_DATABASE_URL=.*@127.0.0.1:5432/' .env 2>/dev/null; then $(MAKE) -s db; fi
	$(RUN) catpoop watch

# A systemd user service runs the watcher from this checkout (docs/service.md).
install:
	$(UV_RUN) catpoop service install --checkout "$(CURDIR)" --runtime $(RUNTIME) $(addprefix --extra ,$(EXTRAS))

uninstall:
	$(UV_RUN) catpoop service uninstall

check:
	$(UV_RUN) ruff format --check .
	$(UV_RUN) ruff check .
	$(UV_RUN) ty check

format:
	uv run ruff format .
	uv run ruff check --fix .

# Database tests use CATPOOP_TEST_DATABASE_URL if set, else start PostgreSQL with Testcontainers.
test:
	$(UV_RUN) pytest

config:
	$(RUN) catpoop check-config

import-history:
	$(RUN) catpoop import-history $(ARGS)

# Export the TF detector to ONNX. Downloads SSD MobileNet v2 FPNLite 320 unless SAVED_MODEL is set.
export-detector:
	@test -n "$(OUT)" || { echo "Set OUT, e.g. make export-detector OUT=/mnt/nas/cat-poop/models/pets.onnx"; exit 1; }
	uv run --extra train python -m catpoop.export_detector --output "$(OUT)" $(if $(SAVED_MODEL),--saved-model "$(SAVED_MODEL)")

# JupyterLab for the notebooks in notebooks/ (e.g. exporting a toy model to ONNX).
notebook:
	$(UV_RUN) --extra train --group notebook jupyter lab notebooks

cut-visits:
	$(RUN) catpoop cut-visits

label:
	$(RUN) catpoop label --port $(or $(PORT),8765)

add-visit:
	@test -n "$(OUTCOME)" -a -n "$(CLIPS)" || { echo "Set OUTCOME and CLIPS, e.g. make add-visit OUTCOME=poop CLIPS=clip.mp4"; exit 1; }
	$(RUN) catpoop add-visit $(OUTCOME) $(CLIPS)

# Training needs TensorFlow (train extra); evaluating runs the exported ONNX files only.
train:
	$(UV_RUN) --extra train catpoop train

evaluate:
	$(UV_RUN) catpoop evaluate

# Switches a running watcher reads at once (kept in $XDG_STATE_HOME/catpoop/switches.json).
dnd:
	@test -n "$(FOR)" || { echo "Set FOR, e.g. make dnd FOR=2h"; exit 1; }
	$(UV_RUN) catpoop dnd --for "$(FOR)" $(if $(ALLOW),--allow $(ALLOW))

dnd-off:
	$(UV_RUN) catpoop dnd --off

pee-on:
	$(UV_RUN) catpoop pee-announcements on

pee-off:
	$(UV_RUN) catpoop pee-announcements off

# The Alexa skill runs inside the watcher ([alexa_skill]); this prints its tunnel setup.
alexa-tunnel:
	@$(UV_RUN) catpoop alexa-tunnel
