"""Build the Alexa skill app and run it with uvicorn on a background thread.

It shares the watcher's event log (for the status) and the switches file (for Do Not
Disturb and Pee announcements). Off unless `[alexa_skill] enabled = true`.
"""

import logging
import threading
from collections.abc import Mapping
from zoneinfo import ZoneInfo

import uvicorn
from cryptography.x509.verification import Store
from fastapi import FastAPI

from catpoop.alexa_skill.certificates import HttpCertificates
from catpoop.alexa_skill.endpoint import PATH, router
from catpoop.alexa_skill.request_verifier import RequestVerifier
from catpoop.alexa_skill.skill import AlexaSkill
from catpoop.clock import Clock
from catpoop.communications.switches import Switches
from catpoop.config import AlexaSkillSettings, Config, ConfigError
from catpoop.interfaces import CertificateSource, EventLog

SKILL_ID_ENV = "CATPOOP_ALEXA_SKILL_ID"
log = logging.getLogger(__name__)


def alexa_app(
    config: Config,
    event_log: EventLog,
    clock: Clock,
    environ: Mapping[str, str],
    *,
    certificates: CertificateSource | None = None,
    trusted: Store | None = None,
    switches: Switches | None = None,
) -> FastAPI | None:
    """The skill's FastAPI app, or None when `[alexa_skill]` is off."""
    if not config.alexa_skill.enabled:
        return None
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
    app.state.verifier, app.state.skill = verifier, skill
    app.include_router(router)
    return app


def serve_in_background(app: FastAPI, settings: AlexaSkillSettings) -> None:
    """Run `app` with uvicorn on a daemon thread; it ends with the watcher's process."""
    where = {"host": settings.host, "port": settings.port}
    threading.Thread(
        target=uvicorn.run, args=(app,), kwargs=where | {"log_config": None}, daemon=True
    ).start()
    url = f"http://{settings.host}:{settings.port}{PATH}"
    log.info("Alexa skill endpoint at %s (tunnel: %s)", url, settings.tunnel)
