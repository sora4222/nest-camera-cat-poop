# Contributing

Dev rules are in [CLAUDE.md](CLAUDE.md). Run `make check` and `make test` before each commit.
CI (`.github/workflows/ci.yml`) runs `make check`, `make test` and `scripts/pr_size.py` on every pull request push. A pull request may change at most 500 lines of code; docs, notebooks and `uv.lock` do not count.

## Code layout

```
src/catpoop/
  cli.py            `catpoop <command>`; Make targets call it
  config.py         load and check the private config.toml
  domain.py         glossary words as types: Urgency, Presence, Outcome, Frame, Detection, Event
  interfaces.py     small Protocols for every swappable part
  registry.py       slots, the registry, and build_parts (config names -> parts)
  watcher_lock.py   one live watcher per machine
  onnx_session.py   open an ONNX model on the CPU or a GPU (cpu/amd/nvidia extras)
  export_detector.py  TF detector SavedModel -> ONNX (`make export-detector`, train extra)
  parts/            built-in implementations, one per file
    memory_event_log.py   event_log "memory"
    presence_off.py       presence "off" (always Unknown)
    onnx_detector.py      detector "onnx" (TF detector exported to ONNX)
    log_speaker.py        speaker kind "log" (writes to the log)
tests/              one test file per module; fakes only
scripts/pr_size.py  CI check: at most 500 changed code lines per pull request
notebooks/          worked examples, run by tests/test_notebooks.py (`make notebook`)
  export_toy_model_to_onnx.ipynb  a toy Keras model -> ONNX, step by step
docs/               setup, configuration, ADRs
```

## Swappable parts

| Slot | Interface | Config |
|---|---|---|
| `CAMERA` | `CameraSource` | `parts.camera`, options in `[camera]` |
| `DETECTOR` | `Detector` | `parts.detector`, options in `[detector]` |
| `EVENT_RULES` | `EventRules` | `parts.event_rules`, options in `[event_rules]` |
| `EVENT_LOG` | `EventLog` | `parts.event_log`, options in `[event_log]` |
| `PRESENCE` | `PresenceCheck` | `parts.presence`, options in `[presence]` |
| `COMMUNICATIONS` | `CommunicationsHandler` | `parts.communications`, options in `[communications]` |
| `SPEAKER` | `Speaker` | one per `[[speakers]]` entry, chosen by its `kind` |

## Adding an implementation

1. Write a test for it in `tests/`.
2. Add a module in `src/catpoop/parts/` with the class and a factory:
   ```python
   @DEFAULT.part(PRESENCE, "wifi")
   def _create(config: Config, options: Mapping[str, Any]) -> WifiPresence:
       return WifiPresence(options["timeout_minutes"])
   ```
3. Import the module in `src/catpoop/parts/__init__.py`.
4. Add its options to `config.example.toml` (no real values) and a line to the layout above.

`make config` shows which chosen parts are available.
