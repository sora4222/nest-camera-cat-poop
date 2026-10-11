.PHONY: help setup dev check format test config

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
	@echo "make setup   install dependencies, create config.toml and .env if missing"
	@echo "make dev     run the application locally"
	@echo "make check   format check, lint and type check"
	@echo "make format  format and auto-fix lint"
	@echo "make test    run the tests"
	@echo "make config  load the private config and say if it is valid"

# Copy the example files only if the private ones do not exist yet.
setup:
	uv sync
	@test -f config.toml || { cp config.example.toml config.toml && echo "Created config.toml; edit it."; }
	@test -f .env || { cp .env.example .env && echo "Created .env; edit it."; }

dev:
	$(RUN) catpoop check-config

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
