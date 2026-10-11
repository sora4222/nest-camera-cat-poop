import pytest

from catpoop.watcher_lock import WatcherAlreadyRunning, WatcherLock


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
