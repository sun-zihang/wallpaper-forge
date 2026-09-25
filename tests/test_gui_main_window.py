from __future__ import annotations

import json

import pytest


def _window(qapp, tmp_path, monkeypatch, settings: dict | None = None):
    from gui import settings_store
    from gui.main_window import MainWindow

    payload = {"auto_check_update": False}
    payload.update(settings or {})
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)
    return MainWindow("0.0.0-test")


def _teardown(win, qapp):
    win.close()
    win.deleteLater()
    qapp.processEvents()


def _patch_question(monkeypatch, answers: list):
    from gui import main_window as mw

    calls = []

    def _question(*args, **kwargs):
        calls.append(args)
        return answers.pop(0) if answers else mw.QMessageBox.No

    monkeypatch.setattr(mw.QMessageBox, "question", staticmethod(_question))
    return calls


def test_close_declines_when_user_answers_no(qapp, tmp_path, monkeypatch):
    from PySide6.QtGui import QCloseEvent

    from gui import main_window as mw

    win = _window(qapp, tmp_path, monkeypatch)
    thread = win.image_page.batch_thread
    monkeypatch.setattr(thread, "isRunning", lambda: True)
    cancelled = []
    monkeypatch.setattr(thread, "cancel", lambda: cancelled.append(True))
    calls = _patch_question(monkeypatch, [mw.QMessageBox.No])
    ev = QCloseEvent()
    try:
        win.closeEvent(ev)
        assert not ev.isAccepted()
        assert cancelled == []
        assert len(calls) == 1
        assert win._shortcut_event_filter_installed
    finally:
        monkeypatch.setattr(thread, "isRunning", lambda: False)
        _teardown(win, qapp)


def test_close_cancels_running_tasks_and_saves_geometry(qapp, tmp_path, monkeypatch):
    from PySide6.QtGui import QCloseEvent

    from gui import main_window as mw
    from gui import settings_store

    win = _window(qapp, tmp_path, monkeypatch)
    thread = win.image_page.batch_thread
    monkeypatch.setattr(thread, "isRunning", lambda: True)
    cancelled = []
    monkeypatch.setattr(thread, "cancel", lambda: cancelled.append(True))
    waits = []
    monkeypatch.setattr(thread, "wait", lambda ms: waits.append(ms) or True)
    calls = _patch_question(monkeypatch, [mw.QMessageBox.Yes])
    ev = QCloseEvent()
    try:
        win.closeEvent(ev)
        assert ev.isAccepted()
        assert cancelled == [True]
        assert waits == [3000]
        assert len(calls) == 1
        assert not win._shortcut_event_filter_installed
        assert settings_store.load_settings().get("window_geometry")
    finally:
        monkeypatch.setattr(thread, "isRunning", lambda: False)
        _teardown(win, qapp)


def test_close_second_prompt_declines_when_stuck_confirmed(qapp, tmp_path, monkeypatch):
    from PySide6.QtGui import QCloseEvent

    from gui import main_window as mw

    win = _window(qapp, tmp_path, monkeypatch)
    thread = win.image_page.batch_thread
    monkeypatch.setattr(thread, "isRunning", lambda: True)
    cancelled = []
    monkeypatch.setattr(thread, "cancel", lambda: cancelled.append(True))
    monkeypatch.setattr(thread, "wait", lambda ms: False)
    calls = _patch_question(monkeypatch, [mw.QMessageBox.Yes, mw.QMessageBox.No])
    ev = QCloseEvent()
    try:
        win.closeEvent(ev)
        assert not ev.isAccepted()
        assert len(calls) == 2
        assert calls[1][1] == "仍在处理"
        assert "3 秒" in calls[1][2]
        assert cancelled == [True]
    finally:
        monkeypatch.setattr(thread, "isRunning", lambda: False)
        _teardown(win, qapp)


def test_close_second_prompt_accepts_and_waits_again(qapp, tmp_path, monkeypatch):
    from PySide6.QtGui import QCloseEvent

    from gui import main_window as mw

    win = _window(qapp, tmp_path, monkeypatch)
    thread = win.image_page.batch_thread
    monkeypatch.setattr(thread, "isRunning", lambda: True)
    cancelled = []
    monkeypatch.setattr(thread, "cancel", lambda: cancelled.append(True))
    waits = []
    monkeypatch.setattr(thread, "wait", lambda ms: waits.append(ms) or False)
    _patch_question(monkeypatch, [mw.QMessageBox.Yes, mw.QMessageBox.Yes])
    ev = QCloseEvent()
    try:
        win.closeEvent(ev)
        assert ev.isAccepted()
        assert waits == [3000, 1000]
    finally:
        monkeypatch.setattr(thread, "isRunning", lambda: False)
        _teardown(win, qapp)


def test_shortcut_add_files_and_dirs_dispatch_to_current_page(qapp, tmp_path, monkeypatch):
    win = _window(qapp, tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(win.image_page, "_add_files", lambda: calls.append("files"))
    monkeypatch.setattr(win.image_page, "_add_dirs", lambda: calls.append("dirs"))
    try:
        win.stack.setCurrentIndex(0)
        win._shortcut_add_files()
        win._shortcut_add_dirs()
        assert calls == ["files", "dirs"]
    finally:
        _teardown(win, qapp)


def test_shortcut_helpers_are_noop_on_settings_page(qapp, tmp_path, monkeypatch):
    win = _window(qapp, tmp_path, monkeypatch)
    try:
        win.stack.setCurrentIndex(5)
        assert win._current_page() is win.settings_page
        assert win._drop_table() is None
        assert win._current_table() is None
        assert win._batch_is_running() is False
        win._shortcut_add_files()
        win._shortcut_add_dirs()
        win._shortcut_select_all()
        win._shortcut_start()
        win._shortcut_cancel()
    finally:
        _teardown(win, qapp)


def test_shortcut_start_only_clicks_enabled_button(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    infos = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        staticmethod(lambda *args: infos.append(args)),
    )
    win = _window(qapp, tmp_path, monkeypatch)
    clicks = []
    win.image_page.start_btn.clicked.connect(lambda: clicks.append(1))
    try:
        win.stack.setCurrentIndex(0)
        win._shortcut_start()
        assert clicks == [1]
        assert infos, "empty-table information dialog should have been shown"
        win.image_page.start_btn.setEnabled(False)
        win._shortcut_start()
        assert clicks == [1]
    finally:
        _teardown(win, qapp)


def test_drag_enter_ignored_without_local_paths(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QMimeData, QPoint, Qt
    from PySide6.QtGui import QDragEnterEvent

    win = _window(qapp, tmp_path, monkeypatch)
    mime = QMimeData()
    try:
        enter = QDragEnterEvent(QPoint(5, 5), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        win.dragEnterEvent(enter)
        assert not enter.isAccepted()
        assert "拖拽" not in win.status_label.text()
        assert win._drop_status_before is None
    finally:
        _teardown(win, qapp)


def test_drop_ignored_on_settings_page(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
    from PySide6.QtGui import QDragEnterEvent, QDropEvent

    win = _window(qapp, tmp_path, monkeypatch)
    image = tmp_path / "a.png"
    image.write_bytes(b"x")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(image))])
    try:
        win.stack.setCurrentIndex(5)
        enter = QDragEnterEvent(
            QPoint(1, 1),
            Qt.CopyAction,
            mime,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        win.dragEnterEvent(enter)
        assert not enter.isAccepted()
        drop = QDropEvent(QPointF(1, 1), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        win.dropEvent(drop)
        assert not drop.isAccepted()
        assert win._drop_status_before is None
    finally:
        _teardown(win, qapp)


def test_manual_update_check_sets_pending_status(qapp, tmp_path, monkeypatch):
    win = _window(qapp, tmp_path, monkeypatch)
    checks = []
    monkeypatch.setattr(win.update_service, "check_async", lambda: checks.append(1))
    try:
        win._manual_update_check()
        assert checks == [1]
        assert win._manual_check is True
        assert "正在检查更新" in win.status_label.text()
    finally:
        _teardown(win, qapp)


def test_on_no_update_manual_shows_info_auto_stays_silent(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    infos = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *args: infos.append(args)))
    win = _window(qapp, tmp_path, monkeypatch)
    try:
        win._manual_check = True
        win._on_no_update()
        assert len(infos) == 1
        assert "当前已是最新版本" in win.status_label.text()
        assert win._manual_check is False

        win.status_label.setText("就绪")
        win._on_no_update()
        assert len(infos) == 1
        assert win.status_label.text() == "就绪"
    finally:
        _teardown(win, qapp)


def test_on_update_check_failed_manual_warns_auto_stays_silent(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *args: warnings.append(args)))
    win = _window(qapp, tmp_path, monkeypatch)
    try:
        win._manual_check = True
        win._on_update_check_failed("网络超时")
        assert len(warnings) == 1
        assert warnings[0][2] == "网络超时"
        assert "检查更新失败" in win.status_label.text()
        assert win._manual_check is False

        win._on_update_check_failed("仍然失败")
        assert len(warnings) == 1
        assert "检查更新失败" in win.status_label.text()
    finally:
        _teardown(win, qapp)


def test_on_update_available_shows_dialog_and_resets_flag(qapp, tmp_path, monkeypatch):
    from types import SimpleNamespace

    import gui.update_dialog as ud

    shown = []

    class FakeDialog:
        def __init__(self, info, parent):
            shown.append(("init", info.tag))

        def exec(self):
            shown.append("exec")

    monkeypatch.setattr(ud, "UpdateDialog", FakeDialog)
    win = _window(qapp, tmp_path, monkeypatch)
    try:
        win._manual_check = True
        win._on_update_available(SimpleNamespace(tag="v9.9.9"))
        assert shown == [("init", "v9.9.9"), "exec"]
        assert "发现新版本 v9.9.9" in win.status_label.text()
        assert win._manual_check is False
    finally:
        _teardown(win, qapp)


def test_restore_state_tolerates_corrupt_geometry_and_page(qapp, tmp_path, monkeypatch):
    win = _window(
        qapp,
        tmp_path,
        monkeypatch,
        settings={"window_geometry": "!!not-base64!!", "active_page": "oops"},
    )
    try:
        assert win.nav.currentRow() == 0
    finally:
        _teardown(win, qapp)


def test_restore_state_tolerates_out_of_range_page_and_garbage_geometry(
    qapp, tmp_path, monkeypatch
):
    win = _window(
        qapp,
        tmp_path,
        monkeypatch,
        settings={"window_geometry": "YWJj", "active_page": 99},
    )
    try:
        assert win.nav.currentRow() == 0
    finally:
        _teardown(win, qapp)


def test_refresh_ffmpeg_missing_and_ok(qapp, tmp_path, monkeypatch):
    import core.ffmpeg_finder as ff

    monkeypatch.setattr(ff, "ffmpeg_available", lambda: False)
    win = _window(qapp, tmp_path, monkeypatch)
    try:
        assert "未找到 ffmpeg" in win.status_label.text()
        assert not win.video_page.start_btn.isEnabled()

        monkeypatch.setattr(ff, "ffmpeg_available", lambda: True)
        win._refresh_ffmpeg()
        assert win.status_label.text() == "就绪"
        assert win.video_page.start_btn.isEnabled()
    finally:
        _teardown(win, qapp)


def test_shortcut_state_wrappers_and_event_filter_pass_through(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QEvent

    win = _window(qapp, tmp_path, monkeypatch)
    try:
        assert win.cancel_shortcut.isEnabled() is False
        win._sync_shortcut_state_on_batch(1, 2, 3)
        assert win.cancel_shortcut.isEnabled() is False
        win._on_focus_changed(None, win.image_page)
        assert win.eventFilter(win, QEvent(QEvent.Type.Show)) is False
        assert win.eventFilter(win, QEvent(QEvent.Type.Paint)) is False
    finally:
        _teardown(win, qapp)


def test_drop_event_ignores_remote_only_urls(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDropEvent

    win = _window(qapp, tmp_path, monkeypatch)
    mime = QMimeData()
    mime.setUrls([QUrl("https://example.invalid/wallpaper.png")])
    try:
        drop = QDropEvent(QPointF(1, 1), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        win.dropEvent(drop)
        assert not drop.isAccepted()
        assert win._drop_status_before is None
    finally:
        _teardown(win, qapp)


def test_modal_dialog_none_app_returns_false(qapp, tmp_path, monkeypatch):
    from gui import main_window as mw

    class _NoApp:
        @staticmethod
        def instance():
            return None

    win = _window(qapp, tmp_path, monkeypatch)
    orig = mw.QApplication
    try:
        assert win._modal_dialog_is_open() is False
        monkeypatch.setattr(mw, "QApplication", _NoApp)
        assert win._modal_dialog_is_open() is False
    finally:
        mw.QApplication = orig
        _teardown(win, qapp)


def test_sync_shortcut_state_noop_without_shortcut_attr():
    from types import SimpleNamespace

    from gui.main_window import MainWindow

    MainWindow._sync_shortcut_state(SimpleNamespace())


def test_install_shortcut_event_filter_twice_is_noop(qapp, tmp_path, monkeypatch):
    win = _window(qapp, tmp_path, monkeypatch)
    try:
        assert win._shortcut_event_filter_installed is True
        win._install_shortcut_event_filter()
        assert win._shortcut_event_filter_installed is True
    finally:
        _teardown(win, qapp)


def test_auto_check_update_schedules_single_shot(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QTimer

    scheduled = []
    orig_single_shot = QTimer.singleShot
    monkeypatch.setattr(
        QTimer, "singleShot", staticmethod(lambda delay, fn: scheduled.append(delay))
    )
    win = _window(qapp, tmp_path, monkeypatch, settings={"auto_check_update": True})
    try:
        assert 2000 in scheduled
    finally:
        QTimer.singleShot = orig_single_shot
        _teardown(win, qapp)


def test_run_sets_up_app_and_exits(monkeypatch):
    from gui import main_window as mw

    created: dict = {}

    class FakeApp:
        def __init__(self, argv):
            created["argv"] = argv

        def setStyleSheet(self, style):
            created["style"] = bool(style)

        def setApplicationName(self, name):
            created["name"] = name

        def exec(self):
            return 7

    class FakeWin:
        def __init__(self, version):
            created["version"] = version

        def show(self):
            created["shown"] = True

    monkeypatch.setattr("PySide6.QtWidgets.QApplication", FakeApp)
    monkeypatch.setattr("gui.crashlog.install_crash_handler", lambda: created.update(crash=True))
    monkeypatch.setattr(mw, "MainWindow", FakeWin)
    with pytest.raises(SystemExit) as ei:
        mw.run("9.9.9-test")
    assert ei.value.code == 7
    assert created["name"] == "WallpaperConverter"
    assert created["style"] is True
    assert created["version"] == "9.9.9-test"
    assert created["shown"] is True
    assert created["crash"] is True
