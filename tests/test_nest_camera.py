import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import googlenestcam as gnc
import pytest

from catpoop.config import Config, ConfigError
from catpoop.interfaces import CameraLoginExpired
from catpoop.parts.nest_camera import NestCamera
from catpoop.registry import CAMERA, default_registry

AT = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)


@dataclass
class GncFrame:
    """Looks like a googlenestcam frame."""

    image: Any
    time: datetime


class FakeStream:
    """A stream that gives `frames`, then stays open with no new picture."""

    def __init__(self, frames: list[GncFrame], closed: threading.Event) -> None:
        self._frames = frames
        self._closed = closed

    def __enter__(self) -> "FakeStream":
        return self

    def __exit__(self, *exc: object) -> None:
        pass

    def frames(self):
        yield from self._frames
        self._closed.wait(5)


class Connections:
    """Plays one scripted answer per connect: an error to raise or frames to stream."""

    def __init__(self, *answers: BaseException | list[GncFrame]) -> None:
        self._answers = list(answers)
        self.calls = 0
        self.closed = threading.Event()
        self.allow_next = threading.Event()
        """Connects after the first wait for this."""
        self.allow_next.set()

    def __call__(self) -> FakeStream:
        if self.calls:
            self.allow_next.wait(5)
        answer = self._answers[min(self.calls, len(self._answers) - 1)]
        self.calls += 1
        if isinstance(answer, BaseException):
            raise answer
        return FakeStream(answer, self.closed)


def poll(read: Callable[[], Any], until: Callable[[Any], bool]) -> Any:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            value = read()
        except CameraLoginExpired as error:
            value = error
        if until(value):
            return value
        time.sleep(0.005)
    raise AssertionError("timed out")


@pytest.fixture
def opened():
    cameras: list[NestCamera] = []

    def open_camera(connections: Connections) -> NestCamera:
        camera = NestCamera(connections, retry_seconds=0.01)
        cameras.append(camera)
        return camera

    yield open_camera
    for camera in cameras:
        camera.close()


def test_read_gives_each_new_frame_once(opened):
    connections = Connections([GncFrame("picture", AT)])
    camera = opened(connections)
    frame = poll(camera.read, lambda f: f is not None)
    assert (frame.image, frame.taken_at) == ("picture", AT)
    assert camera.read() is None
    connections.closed.set()


def test_refused_login_is_login_expired_until_a_picture_comes_back(opened):
    connections = Connections(gnc.TokenError("refused"), [GncFrame("back", AT)])
    connections.allow_next.clear()
    camera = opened(connections)
    poll(camera.read, lambda v: isinstance(v, CameraLoginExpired))
    connections.allow_next.set()
    frame = poll(camera.read, lambda v: v is not None and not isinstance(v, Exception))
    assert frame.image == "back"
    connections.closed.set()


def test_camera_off_gives_no_picture_and_tries_again(opened):
    connections = Connections(gnc.CameraOffError("off"), [GncFrame("on again", AT)])
    camera = opened(connections)
    frame = poll(camera.read, lambda f: f is not None)
    assert frame.image == "on again"
    assert connections.calls >= 2
    connections.closed.set()


def test_nest_camera_needs_a_device_name():
    config = Config.model_validate(
        {
            "parts": dict.fromkeys(
                ["camera", "detector", "event_rules", "event_log", "presence", "communications"],
                "x",
            ),
            "paths": {"private_data_store": "/data"},
        }
    )
    registry = default_registry()
    assert "nest" in registry.names(CAMERA)
    with pytest.raises(ConfigError, match=r"camera\.device"):
        registry.create(CAMERA, "nest", config, {})
    assert isinstance(registry.create(CAMERA, "nest", config, {"device": "Box"}), NestCamera)
