# The live watcher

`make dev` runs the watcher until Ctrl+C; on the server `make install` runs it as a systemd service instead ([service.md](service.md)). Only one runs per user on a machine (see [setup](setup.md#one-watcher-per-machine)); a second one exits with an error.

## What it does

Every `watcher.check_seconds` (default 0.25) it takes the newest picture from the camera chosen in `[parts]` and runs the detector on it. Visits are found the same way as in [cutting clips](visits.md): a Visit starts once the Cat has been in `visits.litter_box` for `visits.min_seconds`, and ends when it has been gone for `visits.end_gap_seconds`.

Each check, and each of these, is handed to the event rules:

| Observation | When | Carries |
|---|---|---|
| `Seen` | every check with a new picture | the Frame, what the detector found and, every `watcher.surface_check_seconds` while the Litter Box is empty, the Outcome model's scores of the surface |
| `NoPicture` | every check without one | only the time |
| `VisitStarted` | a Visit starts | its frames so far and the Outcome Guess |
| `VisitEnded` | a Visit ends | the frames after the Cat left, the Outcome, the saved Visit's id |
| `CameraOffline` | no picture for `timers.camera_offline_minutes` (once per outage) | when the last picture came |
| `LoginExpired` | Google refuses the camera login (once until pictures come back) | |

Camera Offline also ends a Visit going on. The Events the rules give back go in the event log, then to the communications handler (see [Announcements](#announcements)). If the detector fails on a picture, the error is logged, that picture is skipped (`NoPicture`) and the watcher keeps going.

## Event rules

Event rules "standard" (the default) turn observations into Events. Each has an Urgency; Events marked "log only" go in the event log but are never announced.

| Event | When | Urgency |
|---|---|---|
| `visit_started` | a Visit starts, with the Outcome Guess. Pee guesses are log only when `[event_rules] announce_pee = false` | Info |
| `visit_ended` | a Visit ends, with the Outcome and whether the Guess was right (log only) | Info |
| `poop` | the Outcome is Poop; Poop Reminders start | Normal |
| `poop_reminder` | `timers.poop_reminder_first_minutes` after the Poop, then 2x, 4x, 8x... that, until `poop_reminder_max_minutes` or `poop_reminder_max_count`. The first is always announced; later ones only if a Listener's Presence is Home (Unknown counts as Away), else log only | Normal |
| `poop_gone` | a person was at the Litter Box, and the next surface check no longer scores Poop (log only). Reminders stop | Info |
| `dog_at_poop` | the Dog is in the Litter Box while Poop is there; again only after it was away `dog_gone_seconds` | Urgent |
| `camera_offline` | Camera Offline | Normal |
| `login_expired` | Login Expired, and once more at `timers.login_expired_reminder_at` (in `outcome.timezone`) if pictures have not come back | Normal |

Poop being "no longer seen" comes from the Outcome model scoring the empty litter surface: the watcher runs it every `watcher.surface_check_seconds` when nothing is in the Litter Box. With no Outcome model there is no Poop, so none of this happens.

Event rules "log" are a simpler stand-in: one Event per Visit start and end and camera problem.

## Announcements

Communications handler "standard" (the default) is the one gate every Event goes through. It logs each Event with its Urgency (the Urgency is never spoken). Events marked log only stop there. Any other Event is not said when:

1. it is a Visit start guessing Pee and Pee announcements are off (`make pee-off`; `make pee-on` turns them back on),
2. Quiet Hours are on (`[[quiet_hours]]`, read in `outcome.timezone`) and its `allow` does not list the Urgency,
3. Do Not Disturb is on and does not let the Urgency through (`[communications] dnd_allow`, or `ALLOW` given to `make dnd`),
4. every Listener is Away (Unknown, as with presence "off", does not stop it),
5. `[messages]` has no template for its kind, or
6. the same text was said less than `[communications] repeat_seconds` ago.

Otherwise each `[[speakers]]` entry whose `urgencies` (default: all) lists the Urgency says it. A Speaker that fails is logged and the others still speak. A failing handler is logged and the watcher keeps going.

When Quiet Hours end and Poop is still in the Litter Box (a `poop` Event and no `poop_gone` since), the `poop_after_quiet_hours` message is said once, through the same gate (so Do Not Disturb can still hold it back).

### Do Not Disturb and Pee announcements

These are switched while the watcher runs and take effect at once; they are kept in `switches.json` in `$XDG_STATE_HOME/catpoop` (else `~/.local/state/catpoop`), not in the repo or config:

| Command | Does |
|---|---|
| `make dnd FOR=2h` | Do Not Disturb for 2 hours (also `30m`, `1h30m`, `1d`). `ALLOW="urgent"` or `ALLOW=none` says which Urgencies still get through |
| `make dnd-off` | Do Not Disturb off now |
| `make pee-off` / `make pee-on` | Visit starts guessing Pee are not said / said again |

`[event_rules] announce_pee = false` makes Pee guesses log only for good; the switch is for a while.

## Event log

Event log "sqlite" (the default) keeps every Event in a small SQLite database on the server, at `[event_log] path`; a relative path is inside `$XDG_STATE_HOME/catpoop` (else `~/.local/state/catpoop`). Event log "memory" forgets everything on restart.

The Outcome Guess and Outcome come from the [Outcome model](outcome-model.md). Until one has been trained the watcher still runs, without them.

## Clips of every Visit

Each Visit is recorded to a local MP4, from `visits.padding_seconds` before the Cat was first seen until the Visit ends. It is then stored with the history clips and saved as a Visit waiting for labeling, with `source` `live`, so `make label` builds more training data. If the Private Data Store cannot be written, the Visit still ends and the error is logged.

## Speaker "google"

A `[[speakers]]` entry with `kind = "google"` says Announcements on a Google Home or Nest speaker. The speech is made on the server with [Piper](https://github.com/OHF-Voice/piper1-gpl), so no text leaves the house; the speaker fetches it over the home network and plays it.

- Install with `make setup EXTRAS=google` (with `RUNTIME=cpu`: Piper needs the CPU ONNX Runtime, which cannot sit next to the `amd` or `nvidia` one).
- Get a voice: `uv run python -m piper.download_voices en_US-lessac-medium --download-dir <store>/voices` puts the `.onnx` and `.onnx.json` in the Private Data Store; never in the repo. Check the voice's licence.
- Set `device` to the speaker's name in the Google Home app (a speaker group's name works too) and `voice` to the `.onnx` file.
- The server must be on the same network as the speakers (they are found by mDNS; in Docker use host networking). The speech is served at a random URL on `serve_host`:`serve_port` for two minutes; keep that port inside the home network. If finding by name fails, list the speakers' addresses in `known_hosts`.
- Playing interrupts whatever the speaker was playing. A speaker that cannot be found is logged and found again next time.

## Camera "nest"

Reads a Google Nest camera's live stream with [googlenestcam](https://github.com/sora4222/nest-camera-access-python). Set `[camera] device` to the camera's name in the Google Home app and the `GOOGLENESTCAM_*` secrets in `.env` ([setup](setup.md#camera-login)). When the stream fails it reconnects every `[camera] retry_seconds`. A refused or missing Token is Login Expired: log in again and the watcher picks up the new Token on its next try.

## Speaker "alexa"

Says Announcements on an Alexa device through [Voice Monkey](https://voicemonkey.io/docs/api/announcement.html) (API v3). In Voice Monkey, add a Speaker device and use its id as `device` in a `[[speakers]]` entry with `kind = "alexa"`; `voice` (an Amazon Polly voice) and `chime` are optional. Put the Voice Monkey token in `.env` as `CATPOOP_VOICE_MONKEY_TOKEN` (a 1Password `op://` reference works); it is never logged. The text goes to Voice Monkey and Amazon, and is spoken in Amazon's voice.
