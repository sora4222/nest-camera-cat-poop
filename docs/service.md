# Running as a service

On the Linux server the live watcher runs as a systemd **user** service, `catpoop.service`, from the checkout you install it from. It needs no root, except once to let it run while you are logged out.

## Install

From the checkout the server should run (after `make setup`, with `config.toml` and `.env` filled in and `make dev` working):

```sh
make install                          # same RUNTIME and EXTRAS as make setup, e.g.
make install RUNTIME=cpu EXTRAS=google
sudo loginctl enable-linger $USER     # once: start at boot, keep running after logout
```

`make install` writes `~/.config/systemd/user/catpoop.service` (under `$XDG_CONFIG_HOME` if set), made for this checkout, this user and the `uv` and `op` it finds on your `PATH`, then starts it and enables it. Nothing about the unit is in git. To see what it would write without installing: `uv run catpoop service show --extra google`.

The service runs `uv run --frozen --extra <RUNTIME> ... catpoop watch` in the checkout, so it reads `config.toml` there and keeps state in `~/.local/state/catpoop` like `make dev`. Running `make install` again (from this or another checkout) replaces the unit and restarts the service; there is only ever one, as there is only one watcher per user.

With `[alexa_skill] enabled = true` the service also serves the [Alexa skill](alexa-skill.md); its tunnel (cloudflared or tailscaled) runs as its own service.

`make uninstall` stops and removes the service. It leaves your config, `.env`, state and the service secrets file alone.

## Secrets

The service gets secrets the same way `make dev` does, decided when you run `make install`:

- **`op` on the `PATH` and a `.env` in the checkout**: the service runs `op run --env-file=<checkout>/.env -- uv run ...`, which fills in the `op://` references each time it starts. A service has nobody to unlock the 1Password app, so give `op` a [1Password service account](https://developer.1password.com/docs/service-accounts/) that can read only the cat-poop items, and put its token in the service secrets file:

  ```sh
  mkdir -p ~/.config/catpoop
  install -m 600 /dev/null ~/.config/catpoop/service.env
  $EDITOR ~/.config/catpoop/service.env   # add the line OP_SERVICE_ACCOUNT_TOKEN=ops_...
  systemctl --user restart catpoop
  ```

  `make install` reminds you if this file is missing. The file is outside the repo and only the service reads it (`EnvironmentFile=`); any other variable the service alone should get can go there too.
- **No `op`**: the service runs `uv run --env-file <checkout>/.env ...`, so `.env` must hold plain values. Keep it `chmod 600`.
- **No `.env`**: the service gets no secrets beyond the service secrets file.

Changing `.env` or the service secrets file takes effect on the next restart. Installing or removing `op` takes effect on the next `make install`.

## Logs

The watcher logs to the journal:

```sh
journalctl --user -u catpoop -f              # follow
journalctl --user -u catpoop --since today   # today's
systemctl --user status catpoop              # running or not, last lines
```

Without linger, or on some distributions, user journals need `journalctl --user` from the same user; if it shows nothing, try `sudo journalctl _SYSTEMD_USER_UNIT=catpoop.service`.

## Start, stop, restart

```sh
systemctl --user restart catpoop   # e.g. after editing config.toml or .env
systemctl --user stop catpoop      # until the next restart of the machine
systemctl --user start catpoop
```

If the watcher exits with an error (a bad config, `op` not signed in) systemd starts it again after 30 seconds, and gives up after 5 failures in 10 minutes; fix the problem, then `systemctl --user reset-failed catpoop` and start it. Stopping sends Ctrl+C (SIGINT), so the watcher ends cleanly and drops its lock.

`make dev` cannot run while the service does (one watcher per user, see [setup](setup.md#one-watcher-per-machine)): stop the service first.

## Updates

```sh
git pull
make setup RUNTIME=... EXTRAS=...   # if dependencies changed
systemctl --user restart catpoop
```

Run `make install` again instead of the restart if you moved the checkout, changed `RUNTIME` or `EXTRAS`, or installed or removed `op`. The service runs whatever is checked out, so update the branch it runs from with care; a git worktree works as well as the main checkout.
