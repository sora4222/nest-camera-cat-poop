# Cat poop detector

Watches the Litter Box with a Nest camera and tells the Partner about Visits, Poop and the Dog.
Package `catpoop` under `src/`, Python 3.12+. Words come from [GLOSSARY.md](GLOSSARY.md); use them in code, docs and commits. Decisions are in [docs/adr/](docs/adr/). Code layout is in [CONTRIBUTE.md](CONTRIBUTE.md).

## Commands

- `make setup` once, then `make check` (ruff format, ruff lint, `ty`) and `make test` (pytest) before every commit.
- Use `uv` for everything: `uv run`, `uv add`, `uv sync`. Never `pip` or bare `python`.

## Rules

1. Tests first: write a failing test, make it pass, then tidy. Commit each small step.
2. One responsibility per Python file. Short docstrings on files and public functions.
3. Commit messages use a standard type: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
4. No private data in git: no real names, IP addresses, device names, tokens, clips or pictures. Real values live in `config.toml` and `.env` (both git-ignored) and the Private Data Store on the NAS.
5. External services (Google, Alexa, Voice Monkey, Piper, ONNX models, NAS) sit behind the small interfaces in `src/catpoop/interfaces.py`. Tests use fakes and never touch the network or real hardware.
6. Heavy dependencies (TensorFlow, GPU runtimes) go in the `train`, `amd` or `nvidia` extras; CPU ONNX Runtime is the `cpu` extra (`make` picks one with `RUNTIME`). Tests that need them skip cleanly when they are not installed.
7. Must work in the cloud and in git worktrees: no fixed paths inside the repo for data, and tests use temporary folders (for example the watcher lock).
8. When you add a module, update the layout in CONTRIBUTE.md. Keep README.md short; other docs go in `docs/`.
