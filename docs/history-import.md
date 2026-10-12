# Importing camera history

Past clips of the Litter Box are training data. They are copied into the Private Data Store, never into the repo (see [ADR 0001](adr/0001-training-data-from-history-exports-kept-on-nas.md)). Try the importers in this order:

```sh
make import-history ARGS="takeout ~/Downloads/takeout-001.zip ~/Downloads/takeout-002.zip"
make import-history ARGS="portability"
make import-history ARGS="folder ~/Videos/litter-box"
```

Paths can also be set in `config.toml` under `[history.<importer>]` (see `config.example.toml`). Running an import again is safe: a clip already stored is skipped.

## What is stored

Under `paths.private_data_store`:

- `history/clips/<sha256>.mp4`: the original MP4, byte for byte. The name is its content hash, so the same clip from two sources is kept once.
- `history/clips/<sha256>.json`: `recorded_at` and a list of `sources`, each with the importer, where in that source it was found (`origin`), the original file name, when it was imported, and any JSON that came with it.
- `history/downloads/portability/<job id>/`: archives downloaded from the Data Portability API.

`recorded_at` comes from the clip's JSON when there is a time in it, else from the MP4 header, else it is `null`.

## 1. Google Takeout (`takeout`)

At [takeout.google.com](https://takeout.google.com) deselect everything, tick Google Nest, and export as `.zip` or `.tgz`. Pass every archive part, or the folder they were unpacked to. Every `.mp4` inside is imported, with a `<clip>.json` or `<clip>.mp4.json` beside it as its metadata. Whether Takeout includes camera clips depends on the account and region; the layout is not documented, so check the first export.

## 2. Data Portability API (`portability`)

Exports the `nest.camera_event` resource. Only offered in some countries (for example the EEA); elsewhere the API refuses and the import says why.

1. In the Google Cloud project used for the camera, enable the Data Portability API and add the `https://www.googleapis.com/auth/dataportability.nest.camera_event` scope to the OAuth consent screen. Keep the app in Testing with yourself as a test user.
2. Get a refresh token for that scope once, for example with the [OAuth 2.0 Playground](https://developers.google.com/oauthplayground) using your own client. Choose time-based access if offered, so exports can be repeated.
3. Put it in `.env` as `CATPOOP_PORTABILITY_REFRESH_TOKEN`. The client id and secret default to the camera's; set `CATPOOP_PORTABILITY_CLIENT_ID`/`_SECRET` to use another client.

Refresh tokens of apps in Testing expire after 7 days. The import waits for the export job (it can take hours). If it stops, the job id is in its output: resume with `ARGS="portability --job-id <id>"`. Limit the time range with `start_time`/`end_time` in `[history.portability]`.

## 3. Clips saved by hand (`folder`)

In the Google Home app open the camera's history, open an event and save or download the clip (or use home.google.com). Put the clips in one folder (sub-folders are fine) and import it.
