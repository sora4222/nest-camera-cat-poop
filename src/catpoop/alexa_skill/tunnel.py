"""How to open only `/alexa` to the internet with the tunnel chosen in `[alexa_skill]`.

The tunnel itself runs outside this program (cloudflared's own service, or tailscaled);
this only writes out its setup for this machine's port.
"""

from catpoop.alexa_skill.endpoint import PATH
from catpoop.config import AlexaSkillSettings

_PLACEHOLDER = "litter.example.com"


def _local_url(settings: AlexaSkillSettings) -> str:
    host = "127.0.0.1" if settings.host in ("0.0.0.0", "::", "") else settings.host
    return f"http://{host}:{settings.port}"


def tunnel_setup(settings: AlexaSkillSettings) -> str:
    """Setup text for `settings.tunnel` (docs/alexa-skill.md has the whole story)."""
    if settings.tunnel == "tailscale":
        return _tailscale(settings)
    return _cloudflare(settings)


def _cloudflare(settings: AlexaSkillSettings) -> str:
    hostname = settings.hostname or _PLACEHOLDER
    note = (
        ""
        if settings.hostname
        else f"# Set [alexa_skill] hostname in config.toml; {_PLACEHOLDER} is a placeholder.\n"
    )
    return (
        f"{note}"
        "# Cloudflare Tunnel: in ~/.cloudflared/config.yml (see docs/alexa-skill.md).\n"
        "tunnel: <tunnel id>\n"
        "credentials-file: <home>/.cloudflared/<tunnel id>.json\n"
        "ingress:\n"
        f"  - hostname: {hostname}\n"
        f"    path: ^{PATH}$\n"
        f"    service: {_local_url(settings)}\n"
        "  - service: http_status:404\n"
        f"# Alexa skill endpoint: https://{hostname}{PATH}\n"
    )


def _tailscale(settings: AlexaSkillSettings) -> str:
    return (
        "# Tailscale Funnel: run once; it stays on across restarts (see docs/alexa-skill.md).\n"
        "# WARNING: Funnel makes EVERYTHING served on port 443 of this machine public, not\n"
        "# just /alexa. First check that this shows nothing else on :443 (else move it away):\n"
        "tailscale serve status\n"
        f"tailscale funnel --bg --set-path={PATH} {_local_url(settings)}{PATH}\n"
        f"# Alexa skill endpoint: https://<machine>.<tailnet>.ts.net{PATH}\n"
        "# (`tailscale funnel status` shows the name.)\n"
    )
