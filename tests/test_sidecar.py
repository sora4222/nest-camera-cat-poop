from datetime import UTC, datetime

from catpoop.history.sidecar import sidecar_time

WHEN = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)


def test_iso_time_under_a_time_key():
    assert sidecar_time({"id": "x", "startTime": "2026-03-04T05:06:07Z"}) == WHEN


def test_nested_time_is_found():
    assert (
        sidecar_time({"event": [{"details": {"eventTime": "2026-03-04T05:06:07+00:00"}}]}) == WHEN
    )


def test_epoch_seconds_under_a_timestamp_key():
    assert sidecar_time({"takenTime": {"timestamp": str(int(WHEN.timestamp()))}}) == WHEN


def test_naive_time_is_taken_as_utc():
    assert sidecar_time({"time": "2026-03-04T05:06:07"}) == WHEN


def test_no_time_gives_none():
    assert sidecar_time({"time": "soon", "name": "2026-03-04T05:06:07Z"}) is None
