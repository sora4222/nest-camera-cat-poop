"""Find when a clip was recorded in the JSON that came with it.

The export layouts are not documented, so this looks for the first value under a key
containing `time` that is an ISO time, or epoch seconds under a `timestamp` key.
"""

from datetime import UTC, datetime
from typing import Any


def _as_time(key: str, value: Any) -> datetime | None:
    key = key.lower()
    if "time" not in key:
        return None
    if key == "timestamp" and (
        isinstance(value, int) or (isinstance(value, str) and value.isdigit())
    ):
        try:
            return datetime.fromtimestamp(int(value), UTC)
        except (ValueError, OverflowError, OSError):
            return None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def sidecar_time(metadata: Any) -> datetime | None:
    """The first recording time found in `metadata` (parsed JSON), or None."""
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            found = _as_time(str(key), value) or sidecar_time(value)
            if found:
                return found
    elif isinstance(metadata, list):
        for item in metadata:
            found = sidecar_time(item)
            if found:
                return found
    return None
