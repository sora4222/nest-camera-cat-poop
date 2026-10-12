# Contributing

Dev rules are in [CLAUDE.md](CLAUDE.md). Run `make check` and `make test` before each commit.

## Code layout

```
src/catpoop/
  cli.py            `catpoop <command>`; Make targets call it
  config.py         load and check the private config.toml
  observations.py   what the live watcher hands the event rules
  clock.py          the time now and waiting (SystemClock; tests use a fake)
  state_folder.py   $XDG_STATE_HOME/catpoop, for the server's small state files
  domain.py         glossary words as types: Urgency, Presence, Outcome, OutcomeScores, Frame, Detection, Event
  interfaces.py     small Protocols for every swappable part
  registry.py       slots, the registry, and build_parts (config names -> parts)
  watcher_lock.py   one live watcher per machine
  poop_reminders.py when Poop Reminders are due (1, 2, 4, 8... minutes)
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
    finder.py           find Visits from where the Cat is seen (VisitTracker, find_visits)
    clip_writer.py      write an MP4 frame by frame (PyAV)
    video.py            read clip frames (PyAV), save JPEGs (Pillow)
    cut.py              cut new history clips into Visits with the detector
    store.py            Visit records, their frames and the dataset folders
    manifest.py         dataset/manifest.csv
    retention.py        delete the oldest unlabeled clips over the size limit
    add_visit.py        save a whole clip as one Visit (found by hand, or live)
    labeling_app.py     the labeling page's requests and answers
    labeling_server.py  serve it on localhost (stdlib http.server)
    labeling.html       the labeling page
    command.py          `catpoop cut-visits`, `label`, `add-visit`
  outcome/          the Outcome model: train in TF, run with ONNX Runtime (docs/outcome-model.md)
    features.py         pictures and time of day as model inputs (no TF)
    examples.py         examples from dataset/manifest.csv; split by Visit
    accuracy.py         accuracy overall and per class
    model_files.py      outcome.onnx, outcome_guess.onnx and outcome.json
    publish.py          swap in a training run all at once (`current` symlink)
    onnx_outcome.py     OutcomeModel on the server (ONNX Runtime, no TF)
    evaluate.py         measure an OutcomeModel on held-out Visits
    tf_data.py          examples as a tf.data pipeline (train extra)
    network.py          the Keras network (train extra)
    onnx_export.py      Keras -> ONNX with tf2onnx (train extra)
    train.py            train, export and measure both models (train extra)
    command.py          `catpoop train`, `evaluate`
  communications/   what may be said, and when (docs/watcher.md#announcements)
    quiet_hours.py      which Quiet Hours are on at a moment
    switches.py         Do Not Disturb and Pee announcements, in switches.json in the state folder
    messages.py         spoken text from the Message templates
    command.py          `catpoop dnd`, `pee-announcements` (`make dnd`, `dnd-off`, `pee-on`, `pee-off`)
  speech/           speech for Google speakers (google extra)
    piper_speech.py     text -> wav on this machine with a Piper voice
    audio_server.py     serve wav clips on the LAN at random URLs (stdlib http.server)
    cast_player.py      play a URL on a Google speaker found by name (pychromecast)
  watcher/          the live watcher, `make dev` (docs/watcher.md)
    watcher.py          camera -> detector -> Visits -> event rules -> communications, Camera Offline, Login Expired
    recorder.py         record each live Visit and save it for labeling
    command.py          `catpoop watch`, behind the watcher lock
  parts/            built-in implementations, one per file
    memory_event_log.py   event_log "memory"
    presence_off.py       presence "off" (always Unknown)
    onnx_detector.py      detector "onnx" (TF detector exported to ONNX)
    log_speaker.py        speaker kind "log" (writes to the log)
    google_speaker.py     speaker kind "google" (Piper speech on a Google Home / Nest speaker)
    log_event_rules.py    event_rules "log" (Visits and camera problems straight to Events)
    standard_event_rules.py  event_rules "standard" (Visits, Poop Reminders, Dog at Poop, camera problems)
    sqlite_event_log.py   event_log "sqlite" (SQLite file in the user's state folder)
    standard_communications.py  communications "standard" (the one gate for every Announcement)
    nest_camera.py        camera "nest" (googlenestcam live stream)
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
