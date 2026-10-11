import io
import json
from datetime import UTC, datetime

from fake_mp4 import fake_mp4

from catpoop.history.clip_store import HistoryClipStore
from catpoop.history.importer import HistoryClip

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
RECORDED = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)


def clip(data: bytes, *, source="folder", origin="a/clip.mp4", **kwargs) -> HistoryClip:
    return HistoryClip(
        source, origin, origin.rsplit("/", 1)[-1], lambda: io.BytesIO(data), **kwargs
    )


def test_keeps_the_original_bytes_and_records_where_it_came_from(tmp_path):
    data = fake_mp4(payload=b"frames")
    store = HistoryClipStore(tmp_path)
    saved = store.save(clip(data, recorded_at=RECORDED, metadata={"k": "v"}), NOW)
    assert saved.new
    assert saved.path.read_bytes() == data
    record = json.loads(saved.path.with_suffix(".json").read_text())
    assert record["recorded_at"] == "2026-03-04T05:06:07+00:00"
    assert record["sources"] == [
        {
            "source": "folder",
            "origin": "a/clip.mp4",
            "name": "clip.mp4",
            "imported_at": "2026-10-01T12:00:00+00:00",
            "metadata": {"k": "v"},
        }
    ]


def test_clips_live_under_history_clips_named_by_content(tmp_path):
    saved = HistoryClipStore(tmp_path).save(clip(b"abc"), NOW)
    assert saved.path.parent == tmp_path / "history" / "clips"
    assert saved.path.name == saved.sha256 + ".mp4"


def test_same_clip_twice_is_stored_once(tmp_path):
    store = HistoryClipStore(tmp_path)
    store.save(clip(b"abc"), NOW)
    again = store.save(clip(b"abc"), NOW)
    assert not again.new
    record = json.loads(again.path.with_suffix(".json").read_text())
    assert len(record["sources"]) == 1


def test_same_clip_from_another_source_adds_a_source(tmp_path):
    store = HistoryClipStore(tmp_path)
    store.save(clip(b"abc"), NOW)
    again = store.save(clip(b"abc", source="takeout", origin="x.zip!clip.mp4"), NOW)
    record = json.loads(again.path.with_suffix(".json").read_text())
    assert [s["source"] for s in record["sources"]] == ["folder", "takeout"]


def test_recording_time_falls_back_to_the_mp4_header(tmp_path):
    saved = HistoryClipStore(tmp_path).save(clip(fake_mp4(RECORDED)), NOW)
    record = json.loads(saved.path.with_suffix(".json").read_text())
    assert record["recorded_at"] == "2026-03-04T05:06:07+00:00"


def test_unknown_recording_time_is_null(tmp_path):
    saved = HistoryClipStore(tmp_path).save(clip(b"not an mp4"), NOW)
    record = json.loads(saved.path.with_suffix(".json").read_text())
    assert record["recorded_at"] is None


def test_no_temporary_files_are_left(tmp_path):
    store = HistoryClipStore(tmp_path)
    store.save(clip(b"abc"), NOW)
    store.save(clip(b"abc"), NOW)
    names = sorted(p.name for p in (tmp_path / "history" / "clips").iterdir())
    assert [n.rsplit(".", 1)[1] for n in names] == ["json", "mp4"]


def test_unknown_recording_time_is_filled_in_by_a_later_source(tmp_path):
    store = HistoryClipStore(tmp_path)
    store.save(clip(b"not an mp4"), NOW)
    again = store.save(
        clip(b"not an mp4", source="takeout", origin="x.zip!clip.mp4", recorded_at=RECORDED), NOW
    )
    record = json.loads(again.path.with_suffix(".json").read_text())
    assert record["recorded_at"] == "2026-03-04T05:06:07+00:00"
