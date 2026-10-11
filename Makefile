.PHONY: help setup dev check format test config export-detector import-history cut-visits label add-visit

# ONNX Runtime for the detector: cpu (default), amd or nvidia. E.g. `make dev RUNTIME=nvidia`.
RUNTIME ?= cpu
UV_RUN := uv run --extra $(RUNTIME)

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
	@echo "make setup   first-time setup: private config, .env and dev tools"
	@echo "make dev     install the package and dev tools (RUNTIME=cpu|amd|nvidia)"
	@echo "make check   format check, lint and type check"
	@echo "make format  format and auto-fix lint"
	@echo "make test    run the tests"
	@echo "make config  load the private config and say if it is valid"
	@echo "make export-detector OUT=x.onnx [SAVED_MODEL=dir]  TF detector to ONNX (train extra)"
	@echo "make import-history ARGS=\"takeout|portability|folder [paths]\"  copy past clips to the NAS"
	@echo "make cut-visits  cut new clips into Visits; delete old unlabeled clips over the limit"
	@echo "make label [PORT=8765]  labeling page on http://localhost:PORT/"
	@echo "make add-visit OUTCOME=poop|pee|nothing CLIPS=\"a.mp4 b.mp4\"  clips found by hand to the dataset"

# Copy the example files only if the private ones do not exist yet.
setup: dev
	@test -f config.toml || { cp config.example.toml config.toml && echo "Created config.toml; edit it."; }
	@test -f .env || { cp .env.example .env && echo "Created .env; edit it."; }

dev:
	uv sync --extra $(RUNTIME)

check:
	$(UV_RUN) ruff format --check .
	$(UV_RUN) ruff check .
	$(UV_RUN) ty check

format:
	uv run ruff format .
	uv run ruff check --fix .

test:
	$(UV_RUN) pytest

config:
	$(RUN) catpoop check-config

# Export the TF detector to ONNX. Downloads SSD MobileNet v2 FPNLite 320 unless SAVED_MODEL is set.
export-detector:
	@test -n "$(OUT)" || { echo "Set OUT, e.g. make export-detector OUT=/mnt/nas/cat-poop/models/pets.onnx"; exit 1; }
	uv run --extra train python -m catpoop.export_detector --output "$(OUT)" $(if $(SAVED_MODEL),--saved-model "$(SAVED_MODEL)")

import-history:
	$(RUN) catpoop import-history $(ARGS)

cut-visits:
	$(RUN) catpoop cut-visits

label:
	$(RUN) catpoop label --port $(or $(PORT),8765)

add-visit:
	@test -n "$(OUTCOME)" -a -n "$(CLIPS)" || { echo "Set OUTCOME and CLIPS, e.g. make add-visit OUTCOME=poop CLIPS=clip.mp4"; exit 1; }
	$(RUN) catpoop add-visit $(OUTCOME) $(CLIPS)
