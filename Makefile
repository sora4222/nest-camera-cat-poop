.PHONY: help setup dev check format test config

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
