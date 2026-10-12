# The live watcher

`make dev` runs the watcher until Ctrl+C. Only one runs per user on a machine (see [setup](setup.md#one-watcher-per-machine)); a second one exits with an error.

## What it does

Every `watcher.check_seconds` (default 0.25) it takes the newest picture from the camera chosen in `[parts]` and runs the detector on it. Visits are found the same way as in [cutting clips](visits.md): a Visit starts once the Cat has been in `visits.litter_box` for `visits.min_seconds`, and ends when it has been gone for `visits.end_gap_seconds`.

Each check, and each of these, is handed to the event rules:

| Observation | When | Carries |
|---|---|---|
| `Seen` | every check with a new picture | the Frame and what the detector found |
| `NoPicture` | every check without one | only the time |
| `VisitStarted` | a Visit starts | its frames so far and the Outcome Guess |
| `VisitEnded` | a Visit ends | the frames after the Cat left, the Outcome, the saved Visit's id |
| `CameraOffline` | no picture for `timers.camera_offline_minutes` (once per outage) | when the last picture came |
| `LoginExpired` | Google refuses the camera login (once until pictures come back) | |

Camera Offline also ends a Visit going on. The Events the rules give back go in the event log. Event rules "log" just turn Visits and camera problems into Events and write them to the log.

The Outcome Guess and Outcome come from the [Outcome model](outcome-model.md). Until one has been trained the watcher still runs, without them.

## Clips of every Visit

Each Visit is recorded to a local MP4, from `visits.padding_seconds` before the Cat was first seen until the Visit ends. It is then stored with the history clips and saved as a Visit waiting for labeling, with `source` `live`, so `make label` builds more training data. If the Private Data Store cannot be written, the Visit still ends and the error is logged.

## Camera "nest"

Reads a Google Nest camera's live stream with [googlenestcam](https://github.com/sora4222/nest-camera-access-python). Set `[camera] device` to the camera's name in the Google Home app and the `GOOGLENESTCAM_*` secrets in `.env` ([setup](setup.md#camera-login)). When the stream fails it reconnects every `[camera] retry_seconds`. A refused or missing Token is Login Expired: log in again and the watcher picks up the new Token on its next try.
