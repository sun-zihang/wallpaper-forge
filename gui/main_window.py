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
from gui.pages.settings_page import SettingsPage
from gui.pages.video_page import VideoPage
from gui.styles import DARK_QSS


class MainWindow(QMainWindow):
    def __init__(self, version: str):
        super().__init__()
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
        for label in ("图片转换", "视频转换", "GIF 工具", "设置"):
            QListWidgetItem(label, self.nav)

        self.stack = QStackedWidget()
        self.image_page = ImagePage()
        self.video_page = VideoPage()
        self.gif_page = GifPage()
        self.settings_page = SettingsPage(on_changed=self._apply_settings)
        for page in (
            self.image_page,
            self.video_page,
            self.gif_page,
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

    def _apply_settings(self) -> None:
        from gui.settings_store import load_settings

        s = load_settings()
        for page in (self.image_page, self.video_page, self.gif_page):
            page.apply_settings(s)
        self._refresh_ffmpeg()

    def _refresh_ffmpeg(self) -> None:
        from core.ffmpeg_finder import ffmpeg_available

        ok = ffmpeg_available()
        self.video_page.set_ffmpeg_ok(ok)
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
