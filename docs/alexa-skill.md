# Alexa skill

A custom Alexa skill lets the Partner ask about the Litter Box and flip the switches by voice:

| Say | Does |
|---|---|
| "Alexa, ask litter box is there poop in the box?" | Says whether Poop is in the Litter Box and since when (else when the Cat last visited), and whether Do Not Disturb is on or Pee announcements are off |
| "Alexa, tell litter box to be quiet for two hours" | Do Not Disturb until then (at most a week), letting through the Urgencies in `[communications] dnd_allow`, like `make dnd FOR=2h` |
| "Alexa, tell litter box to stop being quiet" | Do Not Disturb off, like `make dnd-off` |
| "Alexa, tell litter box to turn off pee announcements" / "...turn on pee announcements" | like `make pee-off` / `make pee-on` |

"Alexa, open litter box" lists these. The sample sentences are in [`alexa/interactionModels/custom/en-US.json`](../alexa/interactionModels/custom/en-US.json); add more there and paste it into the console again.

The status comes from the event log: there is Poop after a `poop` Event until a `poop_gone` Event. It looks at the newest 2000 Events only. With event log "memory" it only knows what happened since the watcher started.

## How it runs

The watcher serves the skill while it runs, in a thread: `make dev` and the service from [`make install`](service.md) both do, once `[alexa_skill] enabled = true`. There is no second service. Restart the service after changing `[alexa_skill]` or the skill ID.

```
Alexa cloud --HTTPS--> Cloudflare Tunnel or Tailscale Funnel --> 127.0.0.1:8767/alexa (the watcher)
```

The endpoint listens on `127.0.0.1` only (`[alexa_skill] host`, `port`); the tunnel runs on the same machine and brings requests to it. Nothing else is opened.

## Security

- **Only `/alexa` is public.** The tunnel forwards only that path (other paths get 404 from Cloudflare or are not served by Tailscale), and the endpoint itself answers 404 to any other path and 405 to anything but POST.
- **Every request is checked** before the skill sees it (`src/catpoop/alexa_skill/request_verifier.py`), as Amazon requires for skills hosted as a web service:
  1. the `SignatureCertChainUrl` header is `https://s3.amazonaws.com/echo.api/...` (port 443 if any, after `..` is resolved);
  2. the certificate chain there is for `echo-api.amazon.com`, valid now, and leads to a trusted root (certifi's list);
  3. the `Signature-256` header is that certificate's signature of the exact request body;
  4. the request's timestamp is within 150 seconds of now (keep the server's clock right, e.g. with systemd-timesyncd);
  5. the skill ID in the request is `CATPOOP_ALEXA_SKILL_ID`.

  A request failing any of these gets HTTP 400 and is logged. Chains are fetched once per URL (5 s timeout, no redirects, at most 64 KB) and kept until they expire. Request bodies over 64 KB are refused unread.
- **Secrets**: the skill ID goes in `.env`, best as a 1Password reference. It is not a password (the signature is what keeps others out), but it is private. The tunnel's own credentials stay with cloudflared or tailscaled, outside the repo.

## Set up

### 1. Make the skill

In the [Alexa developer console](https://developer.amazon.com/alexa/console/ask), signed in with the Amazon account the Partner's Echo uses:

1. **Create Skill**: any name, model **Custom**, hosting **Provision your own**, template **Start from Scratch**. Choose the Echo's language (the model in the repo is `en-US`; for `en-AU` or `en-GB`, add that language and paste the same model).
2. **Interaction Model > JSON Editor**: paste `alexa/interactionModels/custom/en-US.json`, then **Save** and **Build**. The invocation name is "litter box"; change it there if you like.
3. Copy the skill ID (`amzn1.ask.skill....`, under **View Skill ID**) into `.env` or 1Password:

   ```sh
   CATPOOP_ALEXA_SKILL_ID=op://Private/cat-poop-alexa-skill/skill_id
   ```

4. Turn it on in `config.toml`:

   ```toml
   [alexa_skill]
   enabled = true
   tunnel = "cloudflare"           # or "tailscale"
   hostname = "litter.example.com" # Cloudflare only
   ```

5. Restart the watcher (`systemctl --user restart catpoop`, or `make dev`). The log says `Alexa skill endpoint at http://127.0.0.1:8767/alexa`.

### 2. Open `/alexa` with a tunnel

`make alexa-tunnel` prints the setup for the tunnel in `[alexa_skill] tunnel`, filled in with your port and host name.

#### Cloudflare Tunnel (default)

Needs a domain on Cloudflare (free plan is fine). The server makes an outgoing connection to Cloudflare; no router ports are opened.

```sh
# install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
cloudflared tunnel login                                   # pick the domain
cloudflared tunnel create catpoop                          # prints the tunnel id, writes ~/.cloudflared/<id>.json
cloudflared tunnel route dns catpoop litter.example.com    # your [alexa_skill] hostname
make alexa-tunnel > ~/.cloudflared/config.yml              # then fill in <tunnel id> and <home>
cloudflared tunnel run catpoop                             # try it; Ctrl+C stops it
sudo cloudflared --config ~/.cloudflared/config.yml service install   # keep it running at boot
```

The config sends only `^/alexa$` on that host name to the endpoint; every other path gets 404 from Cloudflare:

```yaml
ingress:
  - hostname: litter.example.com
    path: ^/alexa$
    service: http://127.0.0.1:8767
  - service: http_status:404
```

The endpoint for the skill is `https://litter.example.com/alexa`.

#### Tailscale Funnel

Needs the server on a tailnet with HTTPS certificates and Funnel allowed for it (the first `tailscale funnel` prints a link to allow it in the admin console). Set `tunnel = "tailscale"`, then:

```sh
tailscale funnel --bg --set-path=/alexa http://127.0.0.1:8767/alexa
tailscale funnel status          # shows https://<machine>.<tailnet>.ts.net/alexa
```

Only `/alexa` is funnelled. `--bg` keeps it on across restarts of the machine; `tailscale funnel reset` turns it off. The endpoint for the skill is `https://<machine>.<tailnet>.ts.net/alexa`.

### 3. Point the skill at it

In the console, **Endpoint**: **HTTPS**, Default Region `https://<your host>/alexa`, and for the certificate choose **"My development endpoint has a certificate from a trusted certificate authority"** (both tunnels give one). **Save**.

### 4. Check

```sh
curl -i -X POST https://<your host>/alexa -d '{}'   # 400: reached the endpoint, unsigned request refused
curl -i https://<your host>/                         # 404 from the tunnel or the endpoint
```

Then in the console's **Test** tab (set to **Development**), type "ask litter box is there poop in the box". The skill is in development mode, so it works on Echos signed in to the same Amazon account without publishing it.

## Troubleshooting

- **"There was a problem with the requested skill's response"** and `Alexa request rejected: ...` in the log: the log line says which check failed. A timestamp failure means the server's clock is off.
- **No log line at all**: the request did not reach the watcher. Check the tunnel is running and the curl checks above; with Tailscale, that `--set-path` and the target both end in `/alexa`.
- **The watcher stops at start with `CATPOOP_ALEXA_SKILL_ID is not set`**: add it to `.env` (and, for the service, make sure `op` can read it: [service secrets](service.md#secrets)).
- **`cannot listen on 127.0.0.1:8767`**: another program uses the port; pick another `[alexa_skill] port` and update the tunnel.
