from __future__ import annotations

import contextlib
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.pages.gif_page import GifPage
from gui.pages.image_page import ImagePage
from gui.pages.rewatermark_page import RewatermarkPage
from gui.pages.settings_page import SettingsPage
from gui.pages.unpack_page import UnpackPage
from gui.pages.video_page import VideoPage
from gui.styles import STYLESHEET


class MainWindow(QMainWindow):
    def __init__(self, version: str):
        super().__init__()
        self._version = version
        self._manual_check = False
        self._drop_status_before = None
        self.shortcuts = {}
        self._shortcut_event_filter_installed = False
        self.setAcceptDrops(True)
        self.setWindowTitle(f"Wallpaper Converter {version} — 壁纸格式转换")
        self.resize(1100, 720)

        central = QWidget()
        central.setObjectName("pageRoot")
        central.setAcceptDrops(True)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.nav = QListWidget()
        self.nav.setFixedWidth(160)
        self.nav.setProperty("class", "nav")
        for label in ("图片转换", "视频转换", "GIF 工具", "解包", "去水印", "设置"):
            QListWidgetItem(label, self.nav)

        self.stack = QStackedWidget()
        self.stack.setAcceptDrops(True)
        self.image_page = ImagePage()
        self.video_page = VideoPage()
        self.gif_page = GifPage()
        self.unpack_page = UnpackPage()
        self.rewatermark_page = RewatermarkPage()
        self.settings_page = SettingsPage(on_changed=self._apply_settings)
        for page in (
            self.image_page,
            self.video_page,
            self.gif_page,
            self.unpack_page,
            self.rewatermark_page,
            self.settings_page,
        ):
            self.stack.addWidget(page)

        body.addWidget(self.nav)
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)

        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("statusBar")
        self.status_label.setContentsMargins(12, 6, 12, 6)
        root.addWidget(self.status_label)

        self.setCentralWidget(central)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self._register_shortcuts()
        self.nav.currentRowChanged.connect(self._sync_shortcut_state)
        self._install_shortcut_event_filter()

        self._apply_settings()
        self._restore_window_state()
        self.nav.currentRowChanged.connect(self._persist_active_page)
        self._refresh_ffmpeg()
        self._init_updates()

    def _drop_table(self):
        page = self.stack.currentWidget()
        return getattr(page, "table", None)

    def _clear_drop_hint(self) -> None:
        if self._drop_status_before is not None:
            if self.status_label.text() == "可拖拽文件/文件夹到当前页面":
                self.status_label.setText(self._drop_status_before)
            self._drop_status_before = None

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mime = event.mimeData()
        has_local_path = any(url.toLocalFile() for url in mime.urls())
        if not has_local_path or self._drop_table() is None:
            event.ignore()
            return
        if self._drop_status_before is None:
            self._drop_status_before = self.status_label.text()
        self.status_label.setText("可拖拽文件/文件夹到当前页面")
        event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._clear_drop_hint()
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        table = self._drop_table()
        if table is None:
            event.ignore()
            return
        paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.toLocalFile()
        ]
        if paths:
            table.add_paths(paths)
            event.acceptProposedAction()
        else:
            event.ignore()
        self._clear_drop_hint()

    def _current_page(self):
        return self.stack.currentWidget()

    def _current_table(self):
        return getattr(self._current_page(), "table", None)

    def _processing_pages(self):
        return (
            self.image_page,
            self.video_page,
            self.gif_page,
            self.unpack_page,
            self.rewatermark_page,
        )

    def _make_shortcut(self, name: str, key: str, callback) -> QShortcut:
        shortcut = QShortcut(QKeySequence(key), self)
        shortcut.setContext(Qt.WindowShortcut)
        shortcut.activated.connect(callback)
        self.shortcuts[name] = shortcut
        return shortcut

    def _register_shortcuts(self) -> None:
        self.add_files_shortcut = self._make_shortcut(
            "add_files", "Ctrl+O", self._shortcut_add_files
        )
        self.add_folder_shortcut = self._make_shortcut(
            "add_folder", "Ctrl+Shift+O", self._shortcut_add_dirs
        )
        self.start_shortcut = self._make_shortcut(
            "start", "Ctrl+Enter", self._shortcut_start
        )
        self.cancel_shortcut = self._make_shortcut(
            "cancel", "Esc", self._shortcut_cancel
        )
        self.select_all_shortcut = self._make_shortcut(
            "select_all", "Ctrl+A", self._shortcut_select_all
        )
        self.shortcut_add_files = self.add_files_shortcut
        self.shortcut_add_folder = self.add_folder_shortcut
        self.shortcut_start = self.start_shortcut
        self.shortcut_cancel = self.cancel_shortcut
        self.shortcut_select_all = self.select_all_shortcut
        for page in self._processing_pages():
            page.thread.started.connect(self._sync_shortcut_state)
            page.thread.finished.connect(self._sync_shortcut_state)
            page.thread.batch_finished.connect(self._sync_shortcut_state_on_batch)
        self._sync_shortcut_state()

    def _shortcut_add_files(self) -> None:
        handler = getattr(self._current_page(), "_add_files", None)
        if callable(handler):
            handler()

    def _shortcut_add_dirs(self) -> None:
        handler = getattr(self._current_page(), "_add_dirs", None)
        if callable(handler):
            handler()

    def _shortcut_start(self) -> None:
        button = getattr(self._current_page(), "start_btn", None)
        if button is not None and button.isEnabled():
            button.click()

    def _shortcut_select_all(self) -> None:
        table = self._current_table()
        if table is not None:
            table.select_all()

    def _batch_is_running(self) -> bool:
        thread = getattr(self._current_page(), "thread", None)
        # Pages without a worker (e.g. settings) fall back to QObject.thread(),
        # a bound method rather than a QThread — treat that as "not running".
        if not callable(getattr(thread, "isRunning", None)):
            return False
        return bool(thread.isRunning())

    def _modal_dialog_is_open(self) -> bool:
        app = QApplication.instance()
        if app is None:
            return False
        if app.activeModalWidget() is not None:
            return True
        return any(
            widget is not self and widget.isVisible() and widget.isModal()
            for widget in app.topLevelWidgets()
        )

    def _sync_shortcut_state_on_batch(self, *args) -> None:
        self._sync_shortcut_state()

    def _sync_shortcut_state(self, *args) -> None:
        if not hasattr(self, "cancel_shortcut"):
            return
        self.cancel_shortcut.setEnabled(
            self._batch_is_running() and not self._modal_dialog_is_open()
        )

    def _shortcut_cancel(self) -> None:
        if self._modal_dialog_is_open() or not self._batch_is_running():
            return
        button = getattr(self._current_page(), "cancel_btn", None)
        if button is not None and button.isEnabled():
            button.click()

    def _on_focus_changed(self, previous, current) -> None:
        self._sync_shortcut_state()

    def eventFilter(self, watched, event) -> bool:
        if event.type() in {
            QEvent.Type.Show,
            QEvent.Type.Hide,
            QEvent.Type.WindowActivate,
            QEvent.Type.WindowDeactivate,
            QEvent.Type.Close,
        }:
            QTimer.singleShot(0, self._sync_shortcut_state)
        return super().eventFilter(watched, event)

    def _install_shortcut_event_filter(self) -> None:
        app = QApplication.instance()
        if app is None or self._shortcut_event_filter_installed:
            return
        app.installEventFilter(self)
        app.focusChanged.connect(self._on_focus_changed)
        self._shortcut_event_filter_installed = True

    def _remove_shortcut_event_filter(self) -> None:
        if not self._shortcut_event_filter_installed:
            return
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
            with contextlib.suppress(RuntimeError, TypeError):
                app.focusChanged.disconnect(self._on_focus_changed)
        self._shortcut_event_filter_installed = False

    def _restore_window_state(self) -> None:
        import base64

        from gui.settings_store import load_settings

        s = load_settings()
        raw = s.get("window_geometry") or ""
        if raw:
            try:
                data = base64.b64decode(str(raw).encode("ascii"), validate=True)
            except (ValueError, TypeError):
                data = b""
            if data:
                self.restoreGeometry(data)
        try:
            page = int(s.get("active_page", 0))
        except (TypeError, ValueError):
            page = 0
        if 0 <= page < self.nav.count():
            self.nav.setCurrentRow(page)

    def _persist_active_page(self, row: int) -> None:
        from gui.settings_store import save_settings

        if 0 <= row < self.nav.count():
            save_settings({"active_page": row})

    def _init_updates(self) -> None:
        from PySide6.QtCore import QTimer

        from gui.settings_store import load_settings
        from gui.update_service import UpdateService

        self.update_service = UpdateService(self._version, self)
        self.update_service.update_available.connect(self._on_update_available)
        self.update_service.no_update.connect(self._on_no_update)
        self.update_service.check_failed.connect(self._on_update_check_failed)
        self.settings_page.manual_update_check.connect(self._manual_update_check)
        if load_settings().get("auto_check_update", True):
            QTimer.singleShot(2000, self.update_service.check_async)

    def _manual_update_check(self) -> None:
        self._manual_check = True
        self.status_label.setText("正在检查更新…")
        self.update_service.check_async()

    def _on_update_available(self, info) -> None:
        from gui.update_dialog import UpdateDialog

        self.status_label.setText(f"发现新版本 {info.tag}")
        dlg = UpdateDialog(info, self)
        dlg.exec()
        self._manual_check = False

    def _on_no_update(self) -> None:
        if self._manual_check:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(self, "检查更新", "当前已是最新版本。")
            self.status_label.setText("当前已是最新版本")
        self._manual_check = False

    def _on_update_check_failed(self, message: str) -> None:
        if self._manual_check:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "检查更新", message)
        self.status_label.setText("检查更新失败（可稍后在设置中重试）")
        self._manual_check = False

    def _apply_settings(self) -> None:
        from gui.settings_store import load_settings

        s = load_settings()
        for page in (
            self.image_page,
            self.video_page,
            self.gif_page,
            self.unpack_page,
            self.rewatermark_page,
        ):
            page.apply_settings(s)
        self._refresh_ffmpeg()

    def _refresh_ffmpeg(self) -> None:
        from core.ffmpeg_finder import ffmpeg_available

        ok = ffmpeg_available()
        self.video_page.set_ffmpeg_ok(ok)
        self.rewatermark_page.set_ffmpeg_ok(ok)
        self.settings_page.refresh_ffmpeg()
        if not ok:
            self.status_label.setText("就绪（未找到 ffmpeg：视频功能不可用）")
        else:
            self.status_label.setText("就绪")

    def closeEvent(self, event) -> None:
        running_pages = [
            p
            for p in (
                self.image_page,
                self.video_page,
                self.gif_page,
                self.unpack_page,
                self.rewatermark_page,
            )
            if p.thread.isRunning()
        ]
        if running_pages:
            ret = QMessageBox.question(
                self,
                "确认退出",
                "仍有任务正在处理，退出将取消未完成的任务。\n确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                event.ignore()
                return
            for p in running_pages:
                p.thread.cancel()
            stuck = [p for p in running_pages if not p.thread.wait(3000)]
            if stuck:
                ret = QMessageBox.question(
                    self,
                    "仍在处理",
                    f"有 {len(stuck)} 个任务没有在 3 秒内停止。\n"
                    "继续退出会中断处理，未完成的输出可能不完整。\n仍要退出吗？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if ret != QMessageBox.Yes:
                    event.ignore()
                    return
                for p in stuck:
                    p.thread.wait(1000)
        self._remove_shortcut_event_filter()
        import base64

        from gui.settings_store import save_settings

        save_settings(
            {
                "window_geometry": base64.b64encode(bytes(self.saveGeometry())).decode(
                    "ascii"
                )
            }
        )
        event.accept()


def run(version: str) -> None:
    import sys

    from PySide6.QtWidgets import QApplication

    from gui.crashlog import install_crash_handler

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    app.setApplicationName("WallpaperConverter")
    install_crash_handler()
    win = MainWindow(version)
    win.show()
    sys.exit(app.exec())
