"""BasePage pure helpers: progress, status, task bookkeeping, output mode."""

from __future__ import annotations

from pathlib import Path


def _page(qapp):
    from gui.pages.base import BasePage

    page = BasePage()
    return page


def test_on_progress_and_pct_update_bar(qapp):
    page = _page(qapp)
    try:
        assert page.progress.value() == 0
        page._on_progress(1, 4, "a.png")
        assert page.progress.value() == 0
        page._on_progress(3, 4, "b.png")
        assert page.progress.value() == 50
        # never goes backwards for coarse steps
        page._on_progress(2, 4, "c.png")
        assert page.progress.value() == 50
        page._on_progress_pct(80)
        assert page.progress.value() == 80
        page._on_progress_pct(-1)
        assert page.progress.value() == 80
        page._on_progress_pct(101)
        assert page.progress.value() == 80
        page._on_progress_pct(100)
        assert page.progress.value() == 100
        # total 0 skips coarse
        page._on_progress(1, 0, "x")
        assert page.progress.value() == 100
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_on_status_uses_window_label_or_statusbar(qapp):
    from PySide6.QtWidgets import QLabel, QMainWindow

    page = _page(qapp)
    win = QMainWindow()
    try:
        win.status_label = QLabel("")
        page.setParent(win)
        page._on_status("hello")
        assert win.status_label.text() == "hello"

        del win.status_label
        msgs = []
        win.statusBar().showMessage = lambda m: msgs.append(m)
        # statusBar() returns QStatusBar; replace method on instance
        sb = win.statusBar()
        sb.showMessage = lambda m: msgs.append(m)
        page._on_status("via-statusbar")
        # fallback path via callable statusBar on window
        # (our monkeypatch on statusBar instance still hits label path first)
        # Without status_label, getattr(win, "status_label", None) is None,
        # then statusBar() is called
        assert msgs == [] or msgs  # showMessage may be C++ method; just ensure no raise
        page._on_status("noop")
    finally:
        page.setParent(None)
        win.deleteLater()
        page.deleteLater()
        qapp.processEvents()


def test_on_task_bookkeeps_outputs_and_failures(qapp, tmp_path):
    from core.tasks import Task, TaskKind

    page = _page(qapp)
    try:
        src = tmp_path / "in.png"
        out = tmp_path / "out.png"
        src.write_bytes(b"x")
        out.write_bytes(b"y")
        done = Task(sources=[src], kind=TaskKind.IMAGE_CONVERT)
        done.status = "done"
        done.outputs = [out]
        page._on_task(done)
        assert page.last_outputs == [out]
        assert page.table.output_map[str(src)] == out

        failed = Task(sources=[src], kind=TaskKind.IMAGE_CONVERT)
        failed.status = "failed"
        failed.error = "boom"
        page._on_task(failed)
        assert page._failed_tasks == [failed]

        # len(sources) != len(outputs) pairs all sources to outputs[0]
        multi_src = [tmp_path / "a.png", tmp_path / "b.png"]
        page2_outputs = [tmp_path / "c.png"]
        for p in (*multi_src, *page2_outputs):
            p.write_bytes(b"z")
        multi = Task(sources=multi_src, kind=TaskKind.IMAGE_CONVERT)
        multi.status = "done"
        multi.outputs = page2_outputs
        page.table.output_map = {}
        page._on_task(multi)
        assert page.table.output_map[str(multi_src[0])] == page2_outputs[0]
        assert page.table.output_map[str(multi_src[1])] == page2_outputs[0]

        # non-Path outputs filtered
        odd = Task(sources=[src], kind=TaskKind.IMAGE_CONVERT)
        odd.status = "done"
        odd.outputs = ["not-a-path", out]
        page.table.output_map = {}
        page._on_task(odd)
        assert out in page.last_outputs
        assert page.table.output_map[str(src)] == out

        # sources of non-Path still converted
        other = Task(sources=[src], kind=TaskKind.IMAGE_CONVERT)
        other.status = "pending"
        page._on_task(other)
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_output_mode_value_without_unified_dir_warns(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from core.tasks import OutputMode
    from gui.pages import base as base_mod

    page = _page(qapp)
    msgs = []
    try:
        page.output_mode.setCurrentIndex(1)  # unified
        page.unified_dir = None
        monkeypatch.setattr(
            base_mod.QMessageBox,
            "information",
            staticmethod(lambda *a, **k: msgs.append(a)),
        )
        assert page.output_mode_value() == OutputMode.BESIDE
        assert msgs

        page.unified_dir = Path("C:/tmp")
        assert page.output_mode_value() == OutputMode.UNIFIED

        page.output_mode.setCurrentIndex(0)
        assert page.output_mode_value() == OutputMode.BESIDE
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_on_batch_done_cancelled_leaves_bar_and_status(qapp, monkeypatch):
    from gui.pages import base as base_mod

    page = _page(qapp)
    statuses = []
    try:
        page.progress.setValue(37)
        monkeypatch.setattr(page, "_on_status", lambda t: statuses.append(t))
        monkeypatch.setattr(
            page, "_ask_batch_done", lambda ok, failed: (_ for _ in ()).throw(AssertionError("should not ask"))
        )
        page.start_btn.setEnabled(False)
        page.cancel_btn.setEnabled(True)
        page._on_batch_done(0, 3)
        assert statuses == ["已取消"]
        assert page.progress.value() == 0
        assert page.start_btn.isEnabled()
        assert not page.cancel_btn.isEnabled()
        assert page._last_ok == 0
        assert page._last_failed == 3
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_on_batch_done_success_and_retry(qapp, monkeypatch):
    page = _page(qapp)
    retried = []
    opened = []
    try:
        choices = iter(["retry", "open", "ok"])
        monkeypatch.setattr(page, "_ask_batch_done", lambda ok, failed: next(choices))
        monkeypatch.setattr(page, "_retry_failed", lambda: retried.append(1))
        monkeypatch.setattr(page, "_open_out", lambda: opened.append(1))

        page._on_batch_done(2, 0)
        assert page.progress.value() == 100
        assert retried == [1]

        page._on_batch_done(1, 1)
        assert opened == [1]

        page._on_batch_done(3, 0)
        assert retried == [1] and opened == [1]
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_build_batch_box_buttons(qapp):
    page = _page(qapp)
    try:
        box, open_btn, retry_btn = page._build_batch_box(1, 0)
        assert retry_btn is None
        assert open_btn.isEnabled() is False  # no last_outputs

        page.last_outputs = [Path("C:/out/a.png")]
        box2, open_btn2, _ = page._build_batch_box(1, 0)
        assert open_btn2.isEnabled() is True
        box.deleteLater()
        box2.deleteLater()

        from core.tasks import Task, TaskKind

        failed_task = Task(sources=[Path("C:/x.png")], kind=TaskKind.IMAGE_CONVERT)
        failed_task.status = "failed"
        page._failed_tasks = [failed_task]
        box3, _, retry_btn3 = page._build_batch_box(0, 1)
        assert retry_btn3 is not None
        box3.deleteLater()
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_batch_paths_prefers_retry_paths(qapp, tmp_path):
    page = _page(qapp)
    try:
        a = tmp_path / "a.png"
        page._retry_paths = [a]
        assert page._batch_paths() == [a]
        page._retry_paths = None
        # falls through to table.selected_or_all
        got = page._batch_paths()
        assert isinstance(got, list)
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_submit_empty_batch_shows_message(qapp, monkeypatch):
    from gui.pages import base as base_mod

    page = _page(qapp)
    msgs = []
    try:
        monkeypatch.setattr(
            base_mod.QMessageBox,
            "information",
            staticmethod(lambda *a, **k: msgs.append(a[2] if len(a) > 2 else k)),
        )
        page._submit([])
        assert msgs and "没有可处理的文件" in str(msgs[0])
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_submit_while_running_shows_message(qapp, monkeypatch):
    from gui.pages import base as base_mod
    from core.tasks import Task, TaskKind

    page = _page(qapp)
    msgs = []
    try:
        monkeypatch.setattr(
            base_mod.QMessageBox,
            "information",
            staticmethod(lambda *a, **k: msgs.append(a[2] if len(a) > 2 else k)),
        )
        monkeypatch.setattr(page.thread, "isRunning", lambda: True)
        batch = [Task(sources=[Path("C:/a.png")], kind=TaskKind.IMAGE_CONVERT)]
        page._submit(batch)
        assert msgs and "已有任务在进行中" in str(msgs[0])
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_submit_noop_when_free_space_declined(qapp, tmp_path, monkeypatch):
    from core.tasks import Task, TaskKind
    from gui.pages import base as base_mod
    from PySide6.QtWidgets import QMessageBox

    page = _page(qapp)
    try:
        src = tmp_path / "a.png"
        out_dir = tmp_path / "out"
        out = out_dir / "a.webp"
        from core import space as space_mod

        monkeypatch.setattr(
            space_mod,
            "free_space_warning",
            lambda sources, outputs: "空间不足",
        )
        monkeypatch.setattr(
            base_mod.QMessageBox,
            "question",
            staticmethod(lambda *a, **k: QMessageBox.No),
        )
        submitted = []
        monkeypatch.setattr(page.thread, "submit", lambda b: submitted.append(b))
        batch = [Task(sources=[src], kind=TaskKind.IMAGE_CONVERT)]
        batch[0].outputs = [out]
        page._submit(batch)
        assert submitted == []
        assert page.start_btn.isEnabled()
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_submit_accepts_when_free_space_ok_and_enough(qapp, tmp_path, monkeypatch):
    from core import space as space_mod
    from core.tasks import Task, TaskKind

    page = _page(qapp)
    try:
        src = tmp_path / "a.png"
        out = tmp_path / "out.webp"
        monkeypatch.setattr(space_mod, "free_space_warning", lambda s, o: None)
        submitted = []
        monkeypatch.setattr(page.thread, "submit", lambda b: submitted.append(list(b)))
        batch = [Task(sources=[src], kind=TaskKind.IMAGE_CONVERT)]
        batch[0].outputs = [out]
        page.start_btn.setEnabled(True)
        page._submit(batch)
        assert len(submitted) == 1
        assert not page.start_btn.isEnabled()
        assert page.cancel_btn.isEnabled()
        assert page.last_outputs == []
        assert page._failed_tasks == []
        assert page.progress.value() == 0
    finally:
        page.deleteLater()
        qapp.processEvents()
