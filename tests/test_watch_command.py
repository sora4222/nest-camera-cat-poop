import logging
import socket
from datetime import UTC, datetime, timedelta

import httpx
import numpy as np
import pytest
from fake_clock import FakeClock

from catpoop.cli import main
from catpoop.config import Config, ConfigError
from catpoop.domain import Detection, Event, Frame, Urgency
from catpoop.parts.memory_event_log import MemoryEventLog
from catpoop.registry import CAMERA, COMMUNICATIONS, DETECTOR, EVENT_LOG, EVENT_RULES, Registry
from catpoop.watcher.command import start_watcher
from catpoop.watcher_lock import WatcherLock

START = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)


class EmptyBox:
    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.reads = 0

    def read(self) -> Frame:
        self.reads += 1
        return Frame(self.clock.now(), np.zeros((8, 8, 3), np.uint8))


class NothingFound:
    def detect(self, frame: Frame) -> list[Detection]:
        return []


class NoEvents:
    def update(self, observation: object) -> list[Event]:
        return []


class CountingCommunications:
    def __init__(self) -> None:
        self.ticks = 0

    def handle(self, event: Event) -> None:
        pass

    def tick(self, at: datetime) -> None:
        self.ticks += 1


def setup(tmp_path, event_log=None, rules=None, communications=None):
    clock = FakeClock(START)
    camera = EmptyBox(clock)
    registry = Registry()
    registry.add(CAMERA, "fake", lambda config, options: camera)
    registry.add(DETECTOR, "fake", lambda config, options: NothingFound())
    registry.add(EVENT_RULES, "fake", lambda config, options: rules or NoEvents())
    registry.add(EVENT_LOG, "fake", lambda config, options: event_log or MemoryEventLog())
    communications = communications or CountingCommunications()
    registry.add(COMMUNICATIONS, "fake", lambda config, options: communications)
    config = Config.model_validate(
        {
            "parts": dict.fromkeys(
                ["camera", "detector", "event_rules", "event_log", "presence", "communications"],
                "fake",
            ),
            "paths": {
                "private_data_store": str(tmp_path / "store"),
                "lock_file": str(tmp_path / "lock" / "watcher.lock"),
            },
            "watcher": {"check_seconds": 0.5},
        }
    )
    return config, registry, clock, camera, communications


def stop_after(checks: int):
    left = iter(range(checks))
    return lambda: next(left, None) is None


def test_watcher_runs_until_stopped_without_an_outcome_model(tmp_path, caplog):
    config, registry, clock, camera, communications = setup(tmp_path)
    with caplog.at_level(logging.WARNING):
        assert start_watcher(config, registry, clock, stop_after(3)) == 0
    assert camera.reads == 3
    assert clock.slept == [0.5, 0.5, 0.5]
    assert communications.ticks == 3
    assert "Outcome model" in caplog.text


def test_a_second_watcher_refuses_to_start(tmp_path, capsys):
    config, registry, clock, camera, _ = setup(tmp_path)
    lock_file = config.paths.lock_file
    assert lock_file is not None
    with WatcherLock(lock_file):
        assert start_watcher(config, registry, clock, stop_after(3)) == 1
    assert camera.reads == 0
    assert "already" in capsys.readouterr().err


def test_watch_reports_a_missing_config(tmp_path, capsys):
    assert main(["watch", "--config", str(tmp_path / "missing.toml")]) == 1
    assert "not found" in capsys.readouterr().err


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def with_skill(config: Config, port: int) -> Config:
    skill = config.alexa_skill.model_copy(update={"enabled": True, "port": port})
    return config.model_copy(update={"alexa_skill": skill})


def test_the_alexa_skill_is_served_while_the_watcher_runs(tmp_path):
    config, registry, clock, _, _ = setup(tmp_path)
    port = free_port()
    statuses = []

    def stop() -> bool:
        with httpx.Client(trust_env=False) as client:
            statuses.append(client.get(f"http://127.0.0.1:{port}/alexa").status_code)
        return len(statuses) >= 2

    environ = {"CATPOOP_ALEXA_SKILL_ID": "amzn1.ask.skill.test"}
    assert start_watcher(with_skill(config, port), registry, clock, stop, environ) == 0
    assert statuses == [405, 405]
    with httpx.Client(trust_env=False) as client, pytest.raises(httpx.ConnectError):
        client.get(f"http://127.0.0.1:{port}/alexa")


def test_an_enabled_alexa_skill_without_its_id_stops_the_watcher(tmp_path):
    config, registry, clock, camera, _ = setup(tmp_path)
    with pytest.raises(ConfigError, match="CATPOOP_ALEXA_SKILL_ID"):
        start_watcher(with_skill(config, free_port()), registry, clock, stop_after(3), {})
    assert camera.reads == 0


class PoopKeeper:
    def __init__(self) -> None:
        self.resumed: list[tuple[datetime, datetime]] = []

    def update(self, observation: object) -> list[Event]:
        return []

    def handle(self, event: Event) -> None:
        pass

    def tick(self, at: datetime) -> None:
        pass

    def resume_poop(self, since: datetime, now: datetime) -> None:
        self.resumed.append((since, now))


def test_poop_in_the_event_log_is_resumed_by_the_rules_and_communications(tmp_path):
    event_log = MemoryEventLog()
    poop_at = START - timedelta(hours=1)
    event_log.record(Event("poop", Urgency.NORMAL, poop_at))
    rules, communications = PoopKeeper(), PoopKeeper()
    config, registry, clock, _, _ = setup(tmp_path, event_log, rules, communications)
    assert start_watcher(config, registry, clock, stop_after(1)) == 0
    assert rules.resumed == communications.resumed == [(poop_at, START)]


def test_no_poop_in_the_event_log_resumes_nothing(tmp_path):
    event_log = MemoryEventLog()
    event_log.record(Event("poop", Urgency.NORMAL, START - timedelta(hours=2)))
    event_log.record(Event("poop_gone", Urgency.INFO, START - timedelta(hours=1)))
    rules = PoopKeeper()
    config, registry, clock, _, _ = setup(tmp_path, event_log, rules)
    assert start_watcher(config, registry, clock, stop_after(1)) == 0
    assert rules.resumed == []
