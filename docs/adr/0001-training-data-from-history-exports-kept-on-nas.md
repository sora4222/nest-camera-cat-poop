# Training data comes from camera history exports and lives on the NAS

The camera package (`googlenestcam`) only reads the live stream, and Google's Device Access API cannot download past clips. So training data is gathered, in order of preference, from Google Takeout, the Google Data Portability API (`nest.camera_event`), clips saved by hand from the Google Home app, and finally a recorder on the live stream. All clips, frames, labels and tokens live in the Private Data Store on the NAS, reached over the home network. They never live in this public repo or inside a worktree, so every worktree shares one copy.

## Considered Options

- **Unofficial Nest history endpoints**: can break at any time and may break Google's terms.
- **Live recorder only**: safe, but would mean weeks of waiting before there is anything to train on.
- **Data in a git-ignored folder in the repo**: one slip leaks private video to a public repo, and each worktree would need its own copy.
