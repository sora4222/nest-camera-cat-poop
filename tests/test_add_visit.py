import csv
from datetime import UTC, datetime

import av
import pytest
from fake_video import write_clip

from catpoop.config import VisitSettings
from catpoop.domain import Outcome
from catpoop.visits.add_visit import add_visit, save_clip_as_visit
from catpoop.visits.store import VisitStore
from catpoop.visits.video import VideoError

NOW = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)
SETTINGS = VisitSettings(frame_seconds=0.5)


def test_whole_clip_goes_straight_into_the_dataset(tmp_path):
    clip = write_clip(tmp_path / "poop-by-hand.mp4", [100] * 8)
    store_path = tmp_path / "store"
    visit = add_visit(clip, Outcome.POOP, store_path, SETTINGS, NOW)
    assert (visit.source, visit.outcome, visit.start, visit.frames) == ("manual", "poop", 0, 4)
    assert visit.end == pytest.approx(2.0)
    assert (
        store_path / "history" / "clips" / f"{visit.clip}.mp4"
    ).read_bytes() == clip.read_bytes()
    assert (store_path / "dataset" / "poop" / visit.id / "frame_0004.jpg").exists()
    with (store_path / "dataset" / "manifest.csv").open() as manifest:
        (row,) = list(csv.DictReader(manifest))
    assert row["source"] == "manual"
    assert VisitStore(store_path).is_scanned(visit.clip)


def test_broken_clip_is_refused_and_not_stored(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"nope")
    with pytest.raises(VideoError):
        add_visit(bad, Outcome.PEE, tmp_path / "store", SETTINGS, NOW)
    assert not (tmp_path / "store" / "history").exists()


def test_clip_saved_as_an_unlabeled_visit_waits_for_labeling(tmp_path):
    clip = write_clip(tmp_path / "live.mp4", [100] * 8)
    store_path = tmp_path / "store"
    recorded = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)
    visit = save_clip_as_visit(clip, store_path, SETTINGS, NOW, source="live", recorded=recorded)
    assert (visit.source, visit.outcome, visit.labeled_at) == ("live", None, None)
    assert visit.recorded_at == recorded.isoformat()
    assert [v.id for v in VisitStore(store_path).unlabeled()] == [visit.id]
    assert (store_path / "visits" / "frames" / visit.id / "frame_0004.jpg").exists()
    assert VisitStore(store_path).is_scanned(visit.clip)


def test_clip_without_video_is_refused_and_not_stored(tmp_path):
    sound = tmp_path / "sound.mp4"
    with av.open(str(sound), "w") as container:
        stream = container.add_stream("aac", rate=8000)
        frame = av.AudioFrame(format="fltp", layout="mono", samples=8000)
        frame.rate = 8000
        for plane in frame.planes:
            plane.update(bytes(plane.buffer_size))
        for packet in [*stream.encode(frame), *stream.encode()]:
            container.mux(packet)
    with pytest.raises(VideoError):
        add_visit(sound, Outcome.PEE, tmp_path / "store", SETTINGS, NOW)
    assert not (tmp_path / "store" / "history").exists()
