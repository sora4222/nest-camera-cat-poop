.PHONY: help setup dev check format test config export-detector notebook

# ONNX Runtime for the detector: cpu (default), amd or nvidia. E.g. `make setup RUNTIME=nvidia`.
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
	@echo "make setup   install dependencies (RUNTIME=cpu|amd|nvidia), create config.toml and .env if missing"
	@echo "make dev     run the application locally"
	@echo "make check   format check, lint and type check"
	@echo "make format  format and auto-fix lint"
	@echo "make test    run the tests"
	@echo "make config  load the private config and say if it is valid"
	@echo "make export-detector OUT=x.onnx [SAVED_MODEL=dir]  TF detector to ONNX (train extra)"
	@echo "make notebook  open JupyterLab on notebooks/ (train extra + notebook group)"

# Copy the example files only if the private ones do not exist yet.
setup:
	uv sync --extra $(RUNTIME)
	@test -f config.toml || { cp config.example.toml config.toml && echo "Created config.toml; edit it."; }
	@test -f .env || { cp .env.example .env && echo "Created .env; edit it."; }

dev:
	$(RUN) catpoop check-config

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

# JupyterLab for the notebooks in notebooks/ (e.g. exporting a toy model to ONNX).
notebook:
	$(UV_RUN) --extra train --group notebook jupyter lab notebooks
