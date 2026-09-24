from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import (
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

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
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
            for p in running_pages:
                if not p.thread.wait(3000):
                    p.thread.wait(1000)
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
