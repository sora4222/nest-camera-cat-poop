import threading

from catpoop.watcher.background_task import BackgroundTask


def test_a_request_runs_the_task_on_another_thread_and_returns_at_once():
    release, ran_on = threading.Event(), []

    def task() -> None:
        release.wait(5)
        ran_on.append(threading.current_thread())

    background = BackgroundTask(task, "test")
    background.request()  # would hang here if it ran on this thread
    release.set()
    assert background.wait(5)
    assert ran_on and ran_on[0] is not threading.current_thread()


def test_requests_while_it_runs_make_one_more_run_after_it():
    started, release, runs = threading.Event(), threading.Event(), []

    def task() -> None:
        runs.append(1)
        started.set()
        release.wait(5)

    background = BackgroundTask(task, "test")
    background.request()
    assert started.wait(5)
    background.request()
    background.request()
    release.set()
    assert background.wait(5)
    assert len(runs) == 2


def test_a_failing_task_is_logged_and_can_run_again(caplog):
    calls = []

    def task() -> None:
        calls.append(1)
        raise OSError("NAS is not mounted")

    background = BackgroundTask(task, "pruning")
    background.request()
    assert background.wait(5)
    background.request()
    assert background.wait(5)
    assert len(calls) == 2
    assert "NAS is not mounted" in caplog.text


def test_waiting_with_nothing_running_returns_at_once():
    assert BackgroundTask(lambda: None, "test").wait(0)
