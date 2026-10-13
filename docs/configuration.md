# Where to change things

All settings live in `config.toml` (git-ignored); `config.example.toml` lists every one. Unknown keys are errors, so typos are caught by `make config`.

| To change | Edit |
|---|---|
| Which camera, detector, event rules, event log, Presence check or communications handler is used | `[parts]`, by registered name |
| Options for one of those | its own table, e.g. `[camera]` |
| Detector model file, GPU or CPU, minimum score, class labels | `[detector]` |
| Where clips and labels are kept | `paths.private_data_store` |
| The one-watcher lock file | `paths.lock_file` |
| Cat and Dog names used in messages | `[household]` |
| Who may hear Announcements | `[[listeners]]` |
| Speakers, and which Urgencies each one says | `[[speakers]]`, each with `name`, `kind` and optional `urgencies` |
| What is said | `[messages]`, one template per Event kind |
| Quiet Hours and which Urgencies still get through | `[[quiet_hours]]` |
| Which Urgencies Do Not Disturb lets through, how soon the same text may be said again | `[communications]` |
| Do Not Disturb now, Pee announcements on or off | not config: `make dnd FOR=2h`, `make dnd-off`, `make pee-on`, `make pee-off` |
| Quiet poop or quiet visits for a while | not config: ask the Alexa skill |
| Camera Offline delay, Poop Reminder timing, Login Expired reminder time | `[timers]` |
| Where past clips are imported from | `[history.takeout]`, `[history.portability]`, `[history.folder]` (see [history-import.md](history-import.md)) |
| How clips are cut into Visits, where the Litter Box is in the picture, the store size limit | `[visits]` (see [visits.md](visits.md)) |
| Where the Outcome model is kept, how it is trained and run | `[outcome]` (see [outcome-model.md](outcome-model.md)) |
| Which Nest camera is watched | `[camera] device` |
| How often the live watcher checks the camera, and the litter surface for Poop | `[watcher] check_seconds`, `surface_check_seconds` |
| Pee announcements, Dog and person labels, how long the Dog must be away | `[event_rules]` |
| Where the event log database is kept | `[event_log] path` |
| Secrets (tokens, passwords) | `.env`, not `config.toml` |

To add a new implementation of a part, see [CONTRIBUTE.md](../CONTRIBUTE.md).
