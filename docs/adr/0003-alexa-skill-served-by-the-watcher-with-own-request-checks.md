# Alexa skill served by the watcher, with its own request checks

The Alexa skill endpoint runs inside the live watcher process, in a thread, when `[alexa_skill] enabled = true`. It shares the watcher's event log (for the status) and the switches file (for Do Not Disturb and Pee announcements), so the systemd service from `make install` needs no second unit. The tunnel (Cloudflare Tunnel by default, or Tailscale Funnel) runs as its own program and is set up once by hand.

Alexa requests are checked with `cryptography` (signature, certificate chain to certifi's roots) in a small module of our own, following Amazon's rules for skills hosted as a web service, and tested with generated certificates.

## Considered Options

- **A second service for the skill**: keeps the skill up when the watcher is down, but needs a second unit, a second process reading the event log, and changes to `make install`. Not worth it for one household; if the watcher is down, the status would be stale anyway.
- **Amazon's `ask-sdk-webservice-support`**: does the same checks, but pulls in `oscrypto`, whose released version fails to load with OpenSSL 3.0.10 and later, plus a whole routing framework for five intents.
- **Lambda-hosted skill**: no tunnel, but the status and switches live on the home server, so it would need its own way in anyway.
