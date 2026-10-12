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
  visits/           cut clips into Visits, label them, keep the dataset (docs/visits.md)
    finder.py           find Visits from where the Cat is seen
    video.py            read clip frames (PyAV), save JPEGs (Pillow)
    cut.py              cut new history clips into Visits with the detector
    store.py            Visit records, their frames and the dataset folders
    manifest.py         dataset/manifest.csv
    retention.py        delete the oldest unlabeled clips over the size limit
    add_visit.py        add a clip found by hand straight to the dataset
    labeling_app.py     the labeling page's requests and answers
    labeling_server.py  serve it on localhost (stdlib http.server)
    labeling.html       the labeling page
    command.py          `catpoop cut-visits`, `label`, `add-visit`
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
