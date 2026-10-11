# Contributing

Dev rules are in [CLAUDE.md](CLAUDE.md). Run `make check` and `make test` before each commit.

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
  history/          import past clips into the Private Data Store (docs/history-import.md)
    importer.py         HistoryClip and the HistoryImporter interface
    command.py          `catpoop import-history`
    run.py              copy an importer's clips into the store
    clip_store.py       history/clips/<sha256>.mp4 + .json record of sources
    archive.py          find MP4s and JSON sidecars in .zip/.tgz/folders
    sidecar.py          recording time from a sidecar's JSON
    mp4_time.py         recording time from the MP4 header
    options.py          read importer options
    takeout.py          importer "takeout" (Google Takeout archives)
    portability.py      importer "portability" (Data Portability API export)
    portability_api.py  PortabilityApi interface, ArchiveState, PortabilityError
    portability_http.py the real Data Portability API client (httpx)
    folder.py           importer "folder" (clips saved by hand)
  parts/            built-in implementations, one per file
    memory_event_log.py   event_log "memory"
    presence_off.py       presence "off" (always Unknown)
    onnx_detector.py      detector "onnx" (TF detector exported to ONNX)
    log_speaker.py        speaker kind "log" (writes to the log)
tests/              one test file per module; fakes only
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
| `HISTORY_IMPORTER` | `HistoryImporter` | `catpoop import-history <name>`, options in `[history.<name>]` |

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
