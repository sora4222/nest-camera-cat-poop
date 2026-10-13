import logging
from datetime import UTC, datetime

import numpy as np
from fake_clock import FakeClock

from catpoop.cli import main
from catpoop.config import Config
from catpoop.domain import Detection, Event, Frame
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


def setup(tmp_path):
    clock = FakeClock(START)
    camera = EmptyBox(clock)
    registry = Registry()
    registry.add(CAMERA, "fake", lambda config, options: camera)
    registry.add(DETECTOR, "fake", lambda config, options: NothingFound())
    registry.add(EVENT_RULES, "fake", lambda config, options: NoEvents())
    registry.add(EVENT_LOG, "fake", lambda config, options: MemoryEventLog())
    communications = CountingCommunications()
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
