from __future__ import annotations

import sys

import pytest


def test_darkroom_tokens_and_stylesheet(qapp):
    from gui import styles

    assert styles.BG == "#14171c"
    assert styles.PANEL == "#1a1e24"
    assert styles.PANEL_HI == "#20252d"
    assert styles.BORDER == "#2a303a"
    assert styles.TEXT == "#e8eaee"
    assert styles.DIM == "#9aa3b0"
    assert styles.FAINT == "#6b7482"
    assert styles.ACCENT == "#e0a458"
    assert styles.ACCENT_TEXT == "#17130c"
    assert styles.OK == "#86b06a"
    assert styles.FAIL == "#d97a72"
    assert styles.RUNNING == "#e0a458"
    assert styles.STYLESHEET
    assert "rgba(224, 164, 88, 28)" in styles.STYLESHEET
    qapp.setStyleSheet(styles.STYLESHEET)


def test_file_table_uses_status_tokens_and_mono_font(qapp, tmp_path):
    from gui.styles import ACCENT, FAINT, FAIL, OK
    from gui.widgets.file_table import FileTable

    source = tmp_path / "clip.mp4"
    source.write_bytes(b"x")
    table = FileTable({".mp4"})
    table.add_paths([source])
    item = table.table.item(0, 3)

    for status, color in (
        ("pending", FAINT),
        ("running", ACCENT),
        ("done", OK),
        ("failed", FAIL),
        ("cancelled", FAINT),
    ):
        table.set_status_for_path(source, status)
        assert item.foreground().color().name().lower() == color.lower()
        assert item.font().family() == "Consolas"

    assert table.table.item(0, 0).font().family() == "Consolas"
    assert table.table.item(0, 2).font().family() == "Consolas"
    table.deleteLater()
    qapp.processEvents()


@pytest.fixture
def video_page(qapp, tmp_path, monkeypatch):
    from gui.pages import video_page as module

    monkeypatch.setattr(module, "ffmpeg_available", lambda: True)
    page = module.VideoPage()
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"x")
    page.table.add_paths([source])
    submitted = []
    monkeypatch.setattr(page, "_submit", lambda batch: submitted.append(list(batch)))
    yield page, submitted
    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_video_frames_at_seconds_are_normalized_and_forwarded(video_page):
    page, submitted = video_page
    page.mode.setCurrentText("截取帧")
    page.frame_mode.setCurrentText("指定时间点")
    page.at_seconds_edit.setText("2, 0.5, 10, 0.5")

    page.start_batch()

    assert len(submitted) == 1
    task = submitted[0][0]
    assert task.params["at_seconds"] == [0.5, 2.0, 10.0]
    assert "every_seconds" not in task.params


def test_video_frames_interval_keeps_existing_every_parameter(video_page):
    page, submitted = video_page
    page.mode.setCurrentText("截取帧")
    page.every.setValue(2.5)

    page.start_batch()

    task = submitted[0][0]
    assert task.params["every_seconds"] == 2.5
    assert "at_seconds" not in task.params


@pytest.mark.parametrize("value", ["", "0", "-1", "abc", "0, nope"])
def test_video_frames_rejects_invalid_at_seconds(video_page, monkeypatch, value):
    page, submitted = video_page
    page.mode.setCurrentText("截取帧")
    page.frame_mode.setCurrentText("指定时间点")
    page.at_seconds_edit.setText(value)
    messages = []
    from gui.pages.video_page import QMessageBox

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda *args: messages.append(args)),
    )

    page.start_batch()

    assert submitted == []
    assert messages
    assert "时间点" in messages[0][2]


def test_video_frames_rejects_more_than_200_at_seconds(video_page, monkeypatch):
    page, submitted = video_page
    page.mode.setCurrentText("截取帧")
    page.frame_mode.setCurrentText("指定时间点")
    page.at_seconds_edit.setText(",".join(str(i) for i in range(1, 202)))
    messages = []
    from gui.pages.video_page import QMessageBox

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda *args: messages.append(args)),
    )

    page.start_batch()

    assert submitted == []
    assert "200" in messages[0][2]


def test_main_window_drag_drop_forwards_to_current_table(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
    from PySide6.QtGui import QDragEnterEvent, QDropEvent

    from gui import settings_store
    from gui.main_window import MainWindow

    settings_path = tmp_path / "settings.json"
    settings_path.write_text('{"auto_check_update": false}', encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)
    win = MainWindow("0.0.0-test")
    try:
        image = tmp_path / "image.png"
        nested = tmp_path / "folder" / "nested.jpg"
        ignored = tmp_path / "folder" / "notes.txt"
        nested.parent.mkdir()
        image.write_bytes(b"x")
        nested.write_bytes(b"x")
        ignored.write_bytes(b"x")
        mime = QMimeData()
        mime.setUrls(
            [QUrl.fromLocalFile(str(image)), QUrl.fromLocalFile(str(tmp_path / "folder"))]
        )

        enter = QDragEnterEvent(
            QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier
        )
        win.dragEnterEvent(enter)
        assert enter.isAccepted()
        assert "拖拽" in win.status_label.text()

        drop = QDropEvent(
            QPointF(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier
        )
        win.dropEvent(drop)
        assert {p.name for p in win.image_page.table.all_paths()} == {
            "image.png",
            "nested.jpg",
        }

        leave = __import__("PySide6.QtGui", fromlist=["QDragLeaveEvent"]).QDragLeaveEvent()
        win.dragLeaveEvent(leave)
        assert "拖拽" not in win.status_label.text()
    finally:
        win.close()
        win.deleteLater()
        qapp.processEvents()


def test_write_crash_log_uses_logs_directory_and_traceback(tmp_path):
    from gui.crashlog import write_crash_log

    try:
        raise ValueError("崩溃测试")
    except ValueError as exc:
        path = write_crash_log(exc, tmp_path)

    assert path == tmp_path / "logs" / "last_error.log"
    text = path.read_text(encoding="utf-8")
    assert "ValueError: 崩溃测试" in text
    assert "Traceback" in text


def test_crash_hook_writes_log_and_shows_one_chinese_message(qapp, tmp_path, monkeypatch):
    from gui import crashlog

    monkeypatch.setattr(crashlog, "settings_dir", lambda: tmp_path)
    calls = []
    monkeypatch.setattr(
        crashlog.QMessageBox,
        "critical",
        staticmethod(lambda *args: calls.append(args)),
    )
    previous = sys.excepthook
    monkeypatch.setattr(sys, "excepthook", previous)
    crashlog.install_crash_handler()

    sys.excepthook(ValueError, ValueError("崩溃测试"), None)

    assert len(calls) == 1
    assert calls[0][1] == "程序发生错误"
    assert "日志" in calls[0][2]
    assert (tmp_path / "logs" / "last_error.log").is_file()


def test_crash_hook_never_raises_when_logging_fails(qapp, tmp_path, monkeypatch):
    from gui import crashlog

    monkeypatch.setattr(crashlog, "settings_dir", lambda: tmp_path)

    def fail(*args, **kwargs):
        raise OSError("磁盘不可用")

    monkeypatch.setattr(crashlog, "write_crash_log", fail)
    calls = []
    monkeypatch.setattr(
        crashlog.QMessageBox,
        "critical",
        staticmethod(lambda *args: calls.append(args)),
    )
    previous = sys.excepthook
    monkeypatch.setattr(sys, "excepthook", previous)
    crashlog.install_crash_handler()

    sys.excepthook(OSError, OSError("磁盘不可用"), None)

    assert len(calls) == 1


def test_main_window_smoke_all_processing_pages_have_key_widgets(
    qapp, tmp_path, monkeypatch, capsys
):
    from gui import settings_store
    from gui.main_window import MainWindow
    from gui.styles import STYLESHEET

    settings_path = tmp_path / "settings.json"
    settings_path.write_text('{"auto_check_update": false}', encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)
    old_style = qapp.styleSheet()
    qapp.setStyleSheet(STYLESHEET)
    win = MainWindow("0.0.0-test")
    pages = [
        (win.image_page, ("table", "start_btn", "add_files_btn")),
        (win.video_page, ("table", "mode", "frame_mode", "at_seconds_edit")),
        (win.gif_page, ("table", "mode", "start_btn")),
        (win.unpack_page, ("table", "start_btn")),
        (win.rewatermark_page, ("table", "select_btn", "start_btn")),
    ]
    try:
        for index, (page, names) in enumerate(pages):
            win.stack.setCurrentIndex(index)
            qapp.processEvents()
            assert page is win.stack.currentWidget()
            for name in names:
                assert getattr(page, name) is not None
        error = capsys.readouterr().err
        assert "stylesheet" not in error.lower()
        assert "Unknown property" not in error
    finally:
        win.close()
        win.deleteLater()
        qapp.processEvents()
        qapp.setStyleSheet(old_style)
