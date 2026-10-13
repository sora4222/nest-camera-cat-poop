"""Choose implementations of the swappable parts by the names given in config.

An implementation registers a factory under a name for one slot, for example
`@registry.part(PRESENCE, "wifi")`. `build_parts` makes every part the config asks for.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from catpoop.config import Config, ConfigError, PartKind
from catpoop.history.importer import HistoryImporter
from catpoop.interfaces import (
    CameraSource,
    CommunicationsHandler,
    Detector,
    EventLog,
    EventRules,
    PresenceCheck,
    Speaker,
)

type Factory[T] = Callable[[Config, Mapping[str, Any]], T]
"""Makes a part from the whole config and that part's own options."""


@dataclass(frozen=True)
class Slot[T]:
    """A kind of swappable part; `T` is the interface its implementations follow."""

    kind: str


CAMERA = Slot[CameraSource]("camera")
DETECTOR = Slot[Detector]("detector")
EVENT_RULES = Slot[EventRules]("event_rules")
EVENT_LOG = Slot[EventLog]("event_log")
PRESENCE = Slot[PresenceCheck]("presence")
COMMUNICATIONS = Slot[CommunicationsHandler]("communications")
SPEAKER = Slot[Speaker]("speaker")
HISTORY_IMPORTER = Slot[HistoryImporter]("history_importer")


class UnknownPart(ConfigError):
    """Config names an implementation that is not registered."""


class Registry:
    """Factories by slot and name."""

    def __init__(self) -> None:
        """Start empty."""
        self._factories: dict[tuple[str, str], Factory[Any]] = {}

    def add[T](self, slot: Slot[T], name: str, factory: Factory[T]) -> None:
        """Register `factory` as `name` for `slot`. Each name is used once per slot."""
        key = (slot.kind, name)
        if key in self._factories:
            raise ValueError(f"{slot.kind} {name!r} is already registered")
        self._factories[key] = factory

    def part[T](self, slot: Slot[T], name: str) -> Callable[[Factory[T]], Factory[T]]:
        """Decorator form of `add`."""

        def register(factory: Factory[T]) -> Factory[T]:
            self.add(slot, name, factory)
            return factory

        return register

    def names(self, slot: Slot[Any]) -> list[str]:
        """Registered names for `slot`, sorted."""
        return sorted(name for kind, name in self._factories if kind == slot.kind)

    def create[T](self, slot: Slot[T], name: str, config: Config, options: Mapping[str, Any]) -> T:
        """Make the part registered as `name`, or raise `UnknownPart`."""
        factory = self._factories.get((slot.kind, name))
        if factory is None:
            known = ", ".join(self.names(slot)) or "none"
            raise UnknownPart(f"no {slot.kind} called {name!r}; registered: {known}")
        return factory(config, options)


DEFAULT = Registry()
"""The registry that built-in parts in `catpoop.parts` add themselves to."""


def default_registry() -> Registry:
    """`DEFAULT`, with every built-in part registered."""
    # Local: the parts import this module to register themselves.
    import catpoop.history.folder  # noqa: PLC0415
    import catpoop.history.portability  # noqa: PLC0415
    import catpoop.history.takeout  # noqa: PLC0415
    import catpoop.parts  # noqa: F401, PLC0415  (registers the built-ins)

    return DEFAULT


@dataclass(frozen=True)
class Parts:
    """One of each part, as chosen in config."""

    camera: CameraSource
    detector: Detector
    event_rules: EventRules
    event_log: EventLog
    presence: PresenceCheck
    communications: CommunicationsHandler
    speakers: list[Speaker]


def build_parts(config: Config, registry: Registry) -> Parts:
    """Make every part named in `config.parts`, and one Speaker per `[[speakers]]` entry."""

    def make[T](slot: Slot[T], kind: PartKind) -> T:
        name = getattr(config.parts, kind)
        return registry.create(slot, name, config, config.part_options(kind))

    return Parts(
        camera=make(CAMERA, "camera"),
        detector=make(DETECTOR, "detector"),
        event_rules=make(EVENT_RULES, "event_rules"),
        event_log=make(EVENT_LOG, "event_log"),
        presence=make(PRESENCE, "presence"),
        communications=make(COMMUNICATIONS, "communications"),
        speakers=[
            registry.create(SPEAKER, speaker.kind, config, speaker.model_dump())
            for speaker in config.speakers
        ],
    )
