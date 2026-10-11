# Where to change things

All settings live in `config.toml` (git-ignored); `config.example.toml` lists every one. Unknown keys are errors, so typos are caught by `make config`.

| To change | Edit |
|---|---|
| Which camera, detector, event rules, event log, Presence check or communications handler is used | `[parts]`, by registered name |
| Options for one of those | its own table, e.g. `[camera]` |
| Where clips and labels are kept | `paths.private_data_store` |
| The one-watcher lock file | `paths.lock_file` |
| Cat and Dog names used in messages | `[household]` |
| Who may hear Announcements | `[[listeners]]` |
| Speakers | `[[speakers]]`, each with `name` and `kind` |
| What is said | `[messages]` |
| Quiet Hours and which Urgencies still get through | `[[quiet_hours]]` |
| Camera Offline delay, Poop Reminder timing, Login Expired reminder time | `[timers]` |
| Secrets (tokens, passwords) | `.env`, not `config.toml` |

To add a new implementation of a part, see [CONTRIBUTE.md](../CONTRIBUTE.md).
