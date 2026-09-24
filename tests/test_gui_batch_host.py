"""BatchThread pure-path coverage: submit/cancel/run without starting a real QThread."""

from __future__ import annotations

from core.tasks import Task, TaskKind


def test_batch_thread_submit_stores_batch_and_calls_start(qapp, monkeypatch):
    from gui.batch_host import BatchThread

    thread = BatchThread()
    monkeypatch.setattr(thread, "isRunning", lambda: False)
    started = []
    monkeypatch.setattr(thread, "start", lambda: started.append(True))

    task = Task(sources=[], kind=TaskKind.IMAGE_CONVERT)
    thread.submit([task])

    assert started == [True]
    assert thread._batch == [task]


def test_batch_thread_submit_is_noop_while_running(qapp, monkeypatch):
    from gui.batch_host import BatchThread

    thread = BatchThread()
    seed = Task(sources=[], kind=TaskKind.GIF_SPLIT)
    thread._batch = [seed]
    monkeypatch.setattr(thread, "isRunning", lambda: True)
    started = []
    monkeypatch.setattr(thread, "start", lambda: started.append(True))

    thread.submit([Task(sources=[], kind=TaskKind.IMAGE_CONVERT)])

    assert started == []
    assert thread._batch == [seed]


def test_batch_thread_cancel_forwards_to_runner(qapp, monkeypatch):
    from gui.batch_host import BatchThread

    thread = BatchThread()
    calls = []
    monkeypatch.setattr(thread.runner, "request_cancel", lambda: calls.append(1))
    thread.cancel()
    assert calls == [1]


def test_batch_thread_run_calls_run_batch_and_clears(qapp, monkeypatch):
    from gui.batch_host import BatchThread

    thread = BatchThread()
    batches = []
    monkeypatch.setattr(thread.runner, "run_batch", lambda b: batches.append(list(b)))

    task = Task(sources=[], kind=TaskKind.UNPACK_PKG)
    thread._batch = [task]
    thread.run()

    assert batches == [[task]]
    assert thread._batch == []
