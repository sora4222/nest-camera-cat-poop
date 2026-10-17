"""Whether a person scooped the Poop: they reached into the Litter Box, then it scored no Poop.

Poop scored within `settle_seconds` of the person is ignored (litter settling, a shadow);
later, it means the Poop was left there and a person must come again.
"""

from datetime import datetime, timedelta

from catpoop.domain import Outcome


class Scooping:
    """Follows one scoop of the Poop now in the Litter Box."""

    def __init__(self, settle_seconds: float) -> None:
        """No person seen yet."""
        self._settle = timedelta(seconds=settle_seconds)
        self._person_seen_at: datetime | None = None

    def reset(self) -> None:
        """Forget any person seen (a new Poop, or the Poop is gone)."""
        self._person_seen_at = None

    def person_at_box(self, at: datetime) -> None:
        """A person was reaching into the Litter Box at `at`."""
        self._person_seen_at = at

    def surface_seen(self, at: datetime, best: Outcome) -> bool:
        """Whether the Poop is gone, now that the surface's best Outcome at `at` is `best`."""
        if self._person_seen_at is None:
            return False
        if best is not Outcome.POOP:
            return True
        if at - self._person_seen_at >= self._settle:
            self._person_seen_at = None
        return False
