"""Play an audio URL on a Google Home / Nest speaker, found by its name, with pychromecast.

`pychromecast` comes from the `google` extra and is imported only when a speaker is looked
for. Finding uses mDNS, so the server must be on the same home network as the speakers.
"""

import queue
from collections.abc import Callable, Sequence
from contextlib import suppress
from typing import Any


class FoundCast:
    """A connected cast and the discovery that keeps it reachable, until `close`."""

    def __init__(self, cast: Any, close: Callable[[], None]) -> None:
        """`close` drops the connection and stops discovery."""
        self.cast = cast
        self._close = close

    def close(self) -> None:
        """Drop the connection and stop discovery."""
        self._close()


type Discover = Callable[[str], FoundCast | None]
"""Finds a connected cast device by its name in the Google Home app, or gives None."""


class SpeakerNotFound(LookupError):
    """No Google speaker with that name answered on the home network."""


class SpeakerFailed(RuntimeError):
    """The speaker did not accept the clip, e.g. it could not fetch the URL."""


def find_cast(
    device: str, known_hosts: Sequence[str] | None = None, timeout: float = 10
) -> FoundCast | None:
    """The `pychromecast.Chromecast` called `device`, connected, or None.

    Discovery keeps running until the result is closed: the cast resolves its address
    through discovery's Zeroconf when it connects and when it reconnects.
    """
    import pychromecast

    casts, browser = pychromecast.get_listed_chromecasts(
        friendly_names=[device],
        known_hosts=list(known_hosts) if known_hosts else None,
        discovery_timeout=timeout,
    )
    if not casts:
        browser.stop_discovery()
        return None
    cast = casts[0]

    def close() -> None:
        try:
            cast.disconnect(timeout=timeout)
        finally:
            browser.stop_discovery()

    try:
        cast.wait(timeout=timeout)
    except BaseException:
        close()
        raise
    return FoundCast(cast, close)


class CastPlayer:
    """Plays wav URLs on one Google speaker; finds it again after a failure."""

    def __init__(self, device: str, discover: Discover, volume: float | None = None) -> None:
        """`device` is the speaker's name in the Google Home app; `volume` 0.0-1.0 if given."""
        self._device = device
        self._discover = discover
        self._volume = volume
        self._found: FoundCast | None = None

    def play(self, url: str) -> None:
        """Start playing `url`. Raises `SpeakerNotFound`, or the cast's error."""
        if self._found is None:
            self._found = self._discover(self._device)
            if self._found is None:
                raise SpeakerNotFound(f"no Google speaker called {self._device!r} found")
        cast = self._found.cast
        try:
            if self._volume is not None:
                cast.set_volume(self._volume)
            answers: queue.Queue[tuple[bool, dict | None]] = queue.Queue()
            cast.media_controller.play_media(
                url, "audio/wav", title="Litter box", stream_type="BUFFERED",
                callback_function=lambda sent, response: answers.put((sent, response)),
            )  # fmt: skip
            sent, response = answers.get(timeout=10)  # queue.Empty if no answer
            if not sent or (response or {}).get("type") == "LOAD_FAILED":
                raise SpeakerFailed(f"{self._device!r} did not load the clip: {response}")
        except Exception:
            with suppress(Exception):
                self.close()
            raise

    def close(self) -> None:
        """Drop the kept connection; the next `play` finds the speaker again."""
        found, self._found = self._found, None
        if found is not None:
            found.close()
