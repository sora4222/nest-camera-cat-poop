.PHONY: help setup dev check format test config import-history

# Commands that need secrets run through $(RUN). With the 1Password CLI (`op`)
# installed, `op://` references in .env are filled in; otherwise .env is read as is.
ifneq ($(wildcard .env),)
  ifneq ($(shell command -v op 2>/dev/null),)
    RUN := op run --env-file=.env -- uv run
  else
    RUN := uv run --env-file .env
  endif
else
  RUN := uv run
endif

help:
	@echo "make setup   first-time setup: private config, .env and dev tools"
	@echo "make dev     install the package and dev tools"
	@echo "make check   format check, lint and type check"
	@echo "make format  format and auto-fix lint"
	@echo "make test    run the tests"
	@echo "make config  load the private config and say if it is valid"
	@echo "make import-history ARGS=\"takeout|portability|folder [paths]\"  copy past clips to the NAS"

# Copy the example files only if the private ones do not exist yet.
setup: dev
	@test -f config.toml || { cp config.example.toml config.toml && echo "Created config.toml; edit it."; }
	@test -f .env || { cp .env.example .env && echo "Created .env; edit it."; }

dev:
	uv sync

check:
	uv run ruff format --check .
	uv run ruff check .
	uv run ty check

format:
	uv run ruff format .
	uv run ruff check --fix .

test:
	uv run pytest

config:
	$(RUN) catpoop check-config

import-history:
	$(RUN) catpoop import-history $(ARGS)
