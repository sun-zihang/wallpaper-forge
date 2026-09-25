"""TaskRunner.run_batch edge branches: cancel paths, pct callback, exception mapping."""

from __future__ import annotations

import threading

from core.tasks import Task, TaskKind
from gui import workers as w


def _task(tmp_path, name: str = "a.png") -> Task:
    return Task(sources=[tmp_path / name], kind=TaskKind.IMAGE_CONVERT)


def test_reset_cancel_and_cancel_event_property():
    runner = w.TaskRunner()
    try:
        runner.request_cancel()
        assert runner.cancel_event.is_set()
        runner.reset_cancel()
        assert not runner.cancel_event.is_set()
        assert isinstance(runner.cancel_event, threading.Event)
    finally:
        runner.deleteLater()


def test_run_batch_cancel_midway_skips_remaining(qapp, tmp_path, monkeypatch):
    runner = w.TaskRunner()
    calls = []

    def fake_execute(task, *, progress_cb=None):
        calls.append(task)
        if progress_cb:
            progress_cb(50)
        if len(calls) == 1:
            runner.request_cancel()

    monkeypatch.setattr(w, "execute_task", fake_execute)
    tasks = [_task(tmp_path, "a.png"), _task(tmp_path, "b.png")]
    pcts = []
    statuses = []
    runner.progress_pct.connect(pcts.append)
    runner.task_finished.connect(lambda t: statuses.append(t.status))
    try:
        ok, failed = runner.run_batch(tasks)
    finally:
        runner.deleteLater()
        qapp.processEvents()
    assert (ok, failed) == (0, 2)
    assert tasks[0].status == "cancelled"
    assert tasks[0].error == "已取消"
    assert tasks[1].status == "cancelled"
    assert tasks[1].error == "已取消"
    assert len(calls) == 1
    assert statuses == ["cancelled", "cancelled"]
    assert pcts
    assert "cancel_event" not in tasks[0].params
    assert "cancel_event" not in tasks[1].params


def test_run_batch_exception_with_cancel_text_marks_cancelled(qapp, tmp_path, monkeypatch):
    runner = w.TaskRunner()

    def fake_execute(task, *, progress_cb=None):
        raise RuntimeError("已取消")

    monkeypatch.setattr(w, "execute_task", fake_execute)
    task = _task(tmp_path)
    try:
        ok, failed = runner.run_batch([task])
    finally:
        runner.deleteLater()
        qapp.processEvents()
    assert (ok, failed) == (0, 1)
    assert task.status == "cancelled"
    assert task.error == "已取消"
    assert "cancel_event" not in task.params


def test_run_batch_normal_success_counts_ok(qapp, tmp_path, monkeypatch):
    runner = w.TaskRunner()
    monkeypatch.setattr(w, "execute_task", lambda task, *, progress_cb=None: None)
    tasks = [_task(tmp_path, "a.png"), _task(tmp_path, "b.png")]
    try:
        ok, failed = runner.run_batch(tasks)
    finally:
        runner.deleteLater()
        qapp.processEvents()
    assert (ok, failed) == (2, 0)
    assert all(t.status == "done" for t in tasks)
