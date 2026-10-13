# Contributing

Dev rules are in [CLAUDE.md](CLAUDE.md). Run `make check` and `make test` before each commit.
CI (`.github/workflows/ci.yml`) runs `make check`, `make test` and `scripts/pr_size.py` on every pull request push. A pull request may change at most 500 lines of code; docs, notebooks and `uv.lock` do not count.

## Running the live watcher

`make dev` starts PostgreSQL in Docker (`make db`, for the event log) when .env points at it, and runs the live watcher on this machine until Ctrl+C. `make test` uses that database too when Docker is there; without it the database tests are skipped. Only one runs per user (see [setup](docs/setup.md#one-watcher-per-machine)).

It keeps taking the newest picture from the camera and runs the pet detector on it. When the Cat has stayed in the Litter Box for a moment a Visit starts, and it ends once the Cat has been gone for a while. Each Visit is recorded as a clip and saved for labeling, and the Outcome model guesses what it left behind. The event rules turn all of this, and camera problems, into Events in the event log.

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
  alexa_web.py      Amazon's unofficial Alexa web API: log in, make a device speak
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
  communications/   what may be said, and when
    quiet_hours.py      which Quiet Hours are on at a moment
    switches.py         Do Not Disturb, Quiet Topics and Pee announcements, in switches.json in the state folder
    messages.py         spoken text from the Message templates
    command.py          `catpoop dnd`, `pee-announcements` (`make dnd`, `dnd-off`, `pee-on`, `pee-off`)
  speech/           speech for Google speakers (google extra)
    piper_speech.py     text -> wav on this machine with a Piper voice
    audio_server.py     serve wav clips on the LAN at random URLs (stdlib http.server)
    cast_player.py      play a URL on a Google speaker found by name (pychromecast)
  watcher/          the live watcher, `make dev`
    watcher.py          camera -> detector -> Visits -> event rules -> communications, Camera Offline, Login Expired
    recorder.py         record each live Visit and save it for labeling
    command.py          `catpoop watch`, behind the watcher lock
  alexa_skill/      the Alexa skill the watcher serves on /alexa (docs/alexa-skill.md)
    request_verifier.py is the request from Alexa, for our skill, just now (signature, cert chain, timestamp, skill ID)
    certificates.py     fetch Alexa's signing chain from Amazon's S3 (httpx)
    durations.py        read AMAZON.DURATION values such as PT2H
    spoken_time.py      a time as Alexa should say it ("tomorrow at 7 AM")
    poop_status.py      is there Poop in the Litter Box, from the event log
    skill.py            intents -> switches and spoken answers
    body_limit.py       refuse request bodies over a limit (413)
    endpoint.py         POST /alexa only: verify, then answer (FastAPI router)
    server.py           serve a FastAPI app with uvicorn on a thread
    run.py              run it in a thread beside the watcher
    tunnel.py           Cloudflare Tunnel or Tailscale Funnel setup for /alexa only
    command.py          `catpoop alexa-tunnel` (`make alexa-tunnel`)
  alexa_smart_home/ the Smart Home skill: virtual sensors that fire Alexa routines (docs/alexa-smart-home.md)
    sensors.py          one motion sensor per message kind; which kind a text is
    directives.py       answer Discovery, AcceptGrant and ReportState
    grants.py           Login with Amazon tokens for sending events (state folder)
    event_gateway.py    tell Alexa a sensor saw motion (ChangeReport)
    endpoint.py         POST /alexa/smart-home from our Lambda, with a shared secret
  service/          run the watcher as a systemd user service, `make install` (docs/service.md)
    settings.py         what the service runs: checkout, uv, op, extras, secrets file
    unit_file.py        the unit file text, escaped for systemd
    installer.py        write the unit to ~/.config/systemd/user and start it, or remove it
    systemd_user.py     ServiceManager that runs `systemctl --user`
    command.py          `catpoop service install|uninstall|show`
  parts/            built-in implementations, one per file
    memory_event_log.py   event_log "memory"
    presence_off.py       presence "off" (always Unknown)
    onnx_detector.py      detector "onnx" (TF detector exported to ONNX)
    log_speaker.py        speaker kind "log" (writes to the log)
    alexa_speaker.py      speaker kind "alexa" (fires the Smart Home sensor whose routine says it)
    alexa_web_speaker.py  speaker kind "alexa_web" (an Alexa device by name, unofficial web API)
    google_speaker.py     speaker kind "google" (Piper speech on a Google Home / Nest speaker)
    voice_monkey_speaker.py  speaker kind "voice_monkey" (Alexa through the Voice Monkey announce API)
    log_event_rules.py    event_rules "log" (Visits and camera problems straight to Events)
    standard_event_rules.py  event_rules "standard" (Visits, Poop Reminders, Dog at Poop, camera problems)
    postgres_event_log.py event_log "postgres" (PostgreSQL, URL in .env; `make db` in Docker)
    standard_communications.py  communications "standard" (the one gate for every Announcement)
    nest_camera.py        camera "nest" (googlenestcam live stream)
tests/              one test file per module; fakes only
scripts/pr_size.py  CI check: at most 500 changed code lines per pull request
notebooks/          worked examples, run by tests/test_notebooks.py (`make notebook`)
  export_toy_model_to_onnx.ipynb  a toy Keras model -> ONNX, step by step
docs/               setup, configuration, ADRs
alexa/              the Alexa skill's interaction model, and the Smart Home skill's Lambda
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
