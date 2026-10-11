import os
import stat
import tempfile
from pathlib import Path

import pytest

from catpoop.watcher_lock import (
    UnsafeLockPath,
    WatcherAlreadyRunning,
    WatcherLock,
    default_lock_path,
)


def test_second_lock_on_same_path_is_refused(tmp_path):
    path = tmp_path / "watcher.lock"
    with WatcherLock(path):
        with pytest.raises(WatcherAlreadyRunning):
            with WatcherLock(path):
                pass


def test_lock_can_be_taken_again_after_release(tmp_path):
    path = tmp_path / "watcher.lock"
    with WatcherLock(path):
        pass
    with WatcherLock(path):
        pass


def test_lock_creates_missing_folder(tmp_path):
    path = tmp_path / "run" / "watcher.lock"
    with WatcherLock(path):
        assert path.exists()


def test_different_paths_do_not_block_each_other(tmp_path):
    with WatcherLock(tmp_path / "a.lock"), WatcherLock(tmp_path / "b.lock"):
        pass


def test_default_path_uses_xdg_runtime_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert default_lock_path() == tmp_path / "catpoop-watcher.lock"


def test_default_path_falls_back_to_a_per_user_temp_dir(monkeypatch):
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    expected = Path(tempfile.gettempdir()) / f"catpoop-{os.geteuid()}" / "watcher.lock"
    assert default_lock_path() == expected


def test_missing_folder_is_created_private(tmp_path):
    path = tmp_path / "run" / "watcher.lock"
    with WatcherLock(path):
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_symlink_at_lock_path_is_refused_and_target_kept(tmp_path):
    target = tmp_path / "precious.txt"
    target.write_text("keep me")
    path = tmp_path / "watcher.lock"
    path.symlink_to(target)
    with pytest.raises(UnsafeLockPath):
        with WatcherLock(path):
            pass
    assert target.read_text() == "keep me"


def test_folder_others_can_write_to_is_refused(tmp_path):
    folder = tmp_path / "shared"
    folder.mkdir()
    folder.chmod(0o777)
    with pytest.raises(UnsafeLockPath):
        with WatcherLock(folder / "watcher.lock"):
            pass


def test_folder_owned_by_someone_else_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "geteuid", lambda: tmp_path.stat().st_uid + 1)
    with pytest.raises(UnsafeLockPath):
        with WatcherLock(tmp_path / "watcher.lock"):
            pass


@pytest.mark.skipif(os.geteuid() != 0, reason="needs root to chown")
def test_lock_file_owned_by_someone_else_is_not_truncated(tmp_path):
    path = tmp_path / "watcher.lock"
    path.write_text("not mine")
    os.chown(path, 12345, 12345)
    with WatcherLock(path):
        assert path.read_text() == "not mine"
