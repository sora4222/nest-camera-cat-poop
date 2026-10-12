"""Run the Alexa skill endpoint in a background thread while the watcher runs.

It shares the watcher's event log (for the status) and the switches file (for Do Not
Disturb and Pee announcements). Off unless `[alexa_skill] enabled = true`.
"""

import logging
import threading
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from zoneinfo import ZoneInfo

from cryptography.x509.verification import Store

from catpoop.alexa_skill.certificates import HttpCertificates
from catpoop.alexa_skill.endpoint import PATH, AlexaEndpoint
from catpoop.alexa_skill.request_verifier import RequestVerifier
from catpoop.alexa_skill.routes import Routes
from catpoop.alexa_skill.server import Endpoint, make_server
from catpoop.alexa_skill.skill import AlexaSkill
from catpoop.alexa_smart_home import endpoint as smart_home
from catpoop.alexa_smart_home.directives import SmartHome
from catpoop.alexa_smart_home.grants import Grants
from catpoop.alexa_smart_home.sensors import sensors
from catpoop.clock import Clock
from catpoop.communications.switches import Switches
from catpoop.config import Config, ConfigError
from catpoop.interfaces import CertificateSource, EventLog

SKILL_ID_ENV = "CATPOOP_ALEXA_SKILL_ID"
SMART_HOME_SECRET_ENV = "CATPOOP_ALEXA_SMART_HOME_SECRET"
log = logging.getLogger(__name__)


@contextmanager
def alexa_skill_running(
    config: Config,
    event_log: EventLog,
    clock: Clock,
    environ: Mapping[str, str],
    *,
    grants: Grants | None = None,
    certificates: CertificateSource | None = None,
    trusted: Store | None = None,
    switches: Switches | None = None,
) -> Generator[str | None]:
    """Serve the skill inside the `with`; yields its local URL, or None when it is off."""
    settings = config.alexa_skill
    if not settings.enabled:
        yield None
        return
    skill_id = environ.get(SKILL_ID_ENV, "").strip()
    if not skill_id:
        raise ConfigError(f"[alexa_skill] is enabled but {SKILL_ID_ENV} is not set (in .env)")
    verifier = RequestVerifier(skill_id, certificates or HttpCertificates(), clock, trusted)
    skill = AlexaSkill(
        switches or Switches.default(),
        event_log,
        clock,
        ZoneInfo(config.outcome.timezone),
        cat=config.household.cat,
    )
    routes: dict[str, Endpoint] = {PATH: AlexaEndpoint(verifier, skill)}
    if settings.smart_home:
        secret = environ.get(SMART_HOME_SECRET_ENV, "").strip()
        if not secret:
            raise ConfigError(
                f"[alexa_skill] smart_home is on but {SMART_HOME_SECRET_ENV} is not set"
            )
        grants = grants or Grants.from_env(environ, clock)
        home = SmartHome(sensors(config.messages), grants, clock)
        routes[smart_home.PATH] = smart_home.SmartHomeEndpoint(secret, home)
    try:
        server = make_server(Routes(routes), settings.host, settings.port)
    except OSError as error:
        where = f"{settings.host}:{settings.port}"
        raise ConfigError(f"[alexa_skill] cannot listen on {where}: {error}") from None
    host, port = server.server_address[:2]
    url = f"http://{host}:{port}{PATH}"
    thread = threading.Thread(target=server.serve_forever, name="alexa-skill", daemon=True)
    thread.start()
    log.info("Alexa skill endpoint at %s (tunnel: %s)", url, settings.tunnel)
    try:
        yield url
    finally:
        server.shutdown()
        server.server_close()
