# Cutting clips into Visits and labeling them

After [importing camera history](history-import.md), turn the clips into labeled Visits for training:

```sh
make cut-visits                      # cut every new clip into Visits with the detector
make label                           # open http://localhost:8765/ and label them
make add-visit OUTCOME=poop CLIPS="~/Videos/poop-1.mp4 ~/Videos/poop-2.mp4"
```

## Cutting

`make cut-visits` runs the detector chosen in `[parts]` over every clip in `history/clips` that has not been cut yet, one frame every `visits.frame_seconds`. A Visit starts when the Cat is first seen with the middle of its box inside `visits.litter_box`, and ends when it has been gone for `visits.end_gap_seconds`. Visits shorter than `visits.min_seconds` are dropped; `visits.padding_seconds` is kept on each side. The frames of each Visit are saved as JPEGs. Clips are decoded with [PyAV](https://pyav.basswood-io.com/) (FFmpeg); nothing else needs installing.

Afterwards, if the Private Data Store is bigger than `visits.max_store_gb` (default 500), the oldest clips with no labeled Visit are deleted, with their unlabeled Visits. Clips with a labeled Visit and the dataset are kept forever.

## Labeling

`make label` (or `make label PORT=9000`) serves a small page on this machine only (`127.0.0.1`). It plays the oldest unlabeled Visit; press **Pee** (1), **Poop** (2) or **Nothing** (3) and the next one comes up. Space pauses; the slider steps through frames.

## Clips found by hand

`make add-visit` stores each clip with the history clips and adds all of it to the dataset as one Visit with the given Outcome, without the detector. Use it for short clips that are known to show Pee or Poop.

## What is stored

Under `paths.private_data_store`:

- `dataset/<pee|poop|nothing>/<visit id>/frame_0001.jpg`, ...: frames of labeled Visits, one folder per Visit, ready for `tf.keras.utils.image_dataset_from_directory` or `tf.data`.
- `dataset/manifest.csv`: one row per labeled Visit: `visit_id`, `outcome`, `frames_dir` (relative to `dataset/`), `frame_count`, `clip` (the original MP4, relative to the store), `start_seconds`, `end_seconds`, `recorded_at`, `source` (`detector`, `manual` or `live` from the [watcher](watcher.md)), `labeled_at`.
- `visits/<visit id>.json`: every Visit, labeled or not.
- `visits/frames/<visit id>/`: frames of Visits waiting to be labeled.
- `visits/scanned/<clip sha256>`: the clip has been cut.

The original MP4 of every labeled Visit stays in `history/clips/`. A Visit id is the first 16 characters of its clip's hash and its start in milliseconds, so cutting again gives the same ids.
