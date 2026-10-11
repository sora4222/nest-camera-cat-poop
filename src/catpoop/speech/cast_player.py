"""Play an audio URL on a Google Home / Nest speaker, found by its name, with pychromecast.

`pychromecast` comes from the `google` extra and is imported only when a speaker is looked
for. Finding uses mDNS, so the server must be on the same home network as the speakers.
"""

from collections.abc import Callable, Sequence
from typing import Any

type Discover = Callable[[str], Any]
"""Finds a connected cast device by its name in the Google Home app, or gives None."""


class SpeakerNotFound(LookupError):
    """No Google speaker with that name answered on the home network."""


def find_cast(
    device: str, known_hosts: Sequence[str] | None = None, timeout: float = 10
) -> Any | None:
    """The `pychromecast.Chromecast` called `device`, connected, or None."""
    import pychromecast

    casts, browser = pychromecast.get_listed_chromecasts(
        friendly_names=[device],
        known_hosts=list(known_hosts) if known_hosts else None,
        discovery_timeout=timeout,
    )
    browser.stop_discovery()
    if not casts:
        return None
    cast = casts[0]
    cast.wait(timeout=timeout)
    return cast


class CastPlayer:
    """Plays wav URLs on one Google speaker; finds it again after a failure."""

    def __init__(self, device: str, discover: Discover, volume: float | None = None) -> None:
        """`device` is the speaker's name in the Google Home app; `volume` 0.0-1.0 if given."""
        self._device = device
        self._discover = discover
        self._volume = volume
        self._cast: Any = None

    def play(self, url: str) -> None:
        """Start playing `url`. Raises `SpeakerNotFound`, or the cast's error."""
        if self._cast is None:
            self._cast = self._discover(self._device)
            if self._cast is None:
                raise SpeakerNotFound(f"no Google speaker called {self._device!r} found")
        try:
            if self._volume is not None:
                self._cast.set_volume(self._volume)
            self._cast.media_controller.play_media(
                url, "audio/wav", title="Litter box", stream_type="BUFFERED"
            )
        except Exception:
            self._cast = None
            raise
