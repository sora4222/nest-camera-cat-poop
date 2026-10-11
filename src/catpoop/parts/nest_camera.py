"""Camera "nest": the live stream of a Google Nest camera through `googlenestcam`.

A background thread keeps the newest picture; `read` hands each one out once. When the
stream fails it reconnects after `retry_seconds`. Google refusing the Token (or no Token)
is Login Expired; anything else just means no picture, and the watcher decides when that
is Camera Offline. Secrets come from the `GOOGLENESTCAM_*` variables in `.env`.
"""

import logging
import threading
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from typing import Any

import googlenestcam as gnc

from catpoop.config import Config, ConfigError
from catpoop.domain import Frame
from catpoop.interfaces import CameraLoginExpired
from catpoop.registry import CAMERA, DEFAULT

log = logging.getLogger(__name__)

_LOGIN_ERRORS = (gnc.TokenError, gnc.CredentialsError, gnc.LoginError)

type Connect = Callable[[], AbstractContextManager[Any]]
"""Opens a live stream: a context whose `frames()` gives objects with `image` and `time`."""


class NestCamera:
    """A `CameraSource` fed by a background thread reading a googlenestcam stream."""

    def __init__(self, connect: Connect, retry_seconds: float = 30.0) -> None:
        """`connect` opens the stream; nothing connects until the first `read`."""
        self._connect = connect
        self._retry_seconds = retry_seconds
        self._lock = threading.Lock()
        self._latest: Frame | None = None
        self._login_problem: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def read(self) -> Frame | None:
        """The newest Frame not read before, or None. Raises `CameraLoginExpired`."""
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="nest-camera", daemon=True)
            self._thread.start()
        with self._lock:
            frame, self._latest = self._latest, None
            problem = self._login_problem
        if frame is None and problem is not None:
            raise CameraLoginExpired(problem)
        return frame

    def close(self) -> None:
        """Stop reconnecting. A stream still waiting for a picture ends with the process."""
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                with self._connect() as stream:
                    for picture in stream.frames():
                        with self._lock:
                            self._latest = Frame(picture.time, picture.image)
                            self._login_problem = None
                        if self._stop.is_set():
                            return
                log.warning("camera stream ended")
            except _LOGIN_ERRORS as error:
                log.error("camera login refused: %s", error)
                with self._lock:
                    self._login_problem = str(error)
            except gnc.GoogleNestCamError as error:
                log.warning("no picture from the camera: %s", error)
            except Exception:
                log.exception("camera stream failed")
            self._stop.wait(self._retry_seconds)


@DEFAULT.part(CAMERA, "nest")
def _create(config: Config, options: Mapping[str, Any]) -> NestCamera:
    device = options.get("device")
    if not device:
        raise ConfigError("camera.device: the camera's name in the Google Home app is missing")
    size = options.get("size", 720)

    def connect() -> AbstractContextManager[Any]:
        camera = gnc.Nest(on_missing_token="raise").camera(device)
        return camera.stream(frames="latest", size=size, audio=False)

    return NestCamera(connect, options.get("retry_seconds", 30.0))
