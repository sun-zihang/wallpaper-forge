from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
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
from gui.styles import DARK_QSS


class MainWindow(QMainWindow):
    def __init__(self, version: str):
        super().__init__()
        self._version = version
        self._manual_check = False
        self.setWindowTitle(f"Wallpaper Converter {version} — 壁纸格式转换")
        self.resize(1100, 720)

        central = QWidget()
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
        self.status_label.setContentsMargins(12, 6, 12, 6)
        root.addWidget(self.status_label)

        self.setCentralWidget(central)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        self._apply_settings()
        self._refresh_ffmpeg()
        self._init_updates()

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


def run(version: str) -> None:
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_QSS)
    app.setApplicationName("WallpaperConverter")
    win = MainWindow(version)
    win.show()
    sys.exit(app.exec())
