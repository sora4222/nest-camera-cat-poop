"""Run the Alexa skill endpoint in a background thread while the watcher runs.

It shares the watcher's event log (for the status) and the switches file (for Do Not
Disturb and Pee announcements). Off unless `[alexa_skill] enabled = true`.
"""

import logging
from collections.abc import Generator, Mapping
from contextlib import ExitStack, contextmanager
from zoneinfo import ZoneInfo

from cryptography.x509.verification import Store
from fastapi import FastAPI

from catpoop.alexa_skill.certificates import HttpCertificates
from catpoop.alexa_skill.endpoint import PATH, alexa_router
from catpoop.alexa_skill.request_verifier import RequestVerifier
from catpoop.alexa_skill.server import serving
from catpoop.alexa_skill.skill import AlexaSkill
from catpoop.alexa_smart_home.directives import SmartHome
from catpoop.alexa_smart_home.endpoint import smart_home_router
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
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(alexa_router(verifier, skill))
    if settings.smart_home:
        secret = environ.get(SMART_HOME_SECRET_ENV, "").strip()
        if not secret:
            raise ConfigError(
                f"[alexa_skill] smart_home is on but {SMART_HOME_SECRET_ENV} is not set"
            )
        grants = grants or Grants.from_env(environ, clock)
        home = SmartHome(sensors(config.messages), grants, clock)
        app.include_router(smart_home_router(secret, home))
    with ExitStack() as stack:
        try:
            host, port = stack.enter_context(serving(app, settings.host, settings.port))
        except OSError as error:
            where = f"{settings.host}:{settings.port}"
            raise ConfigError(f"[alexa_skill] cannot listen on {where}: {error}") from None
        url = f"http://{host}:{port}{PATH}"
        log.info("Alexa skill endpoint at %s (tunnel: %s)", url, settings.tunnel)
        yield url
