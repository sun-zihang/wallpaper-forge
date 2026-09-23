from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from core.updater import ReleaseInfo
from gui.update_service import DownloadWorker, UpdateService


class UpdateDialog(QDialog):
    def __init__(self, info: ReleaseInfo, parent=None):
        super().__init__(parent)
        self.setWindowTitle("发现新版本")
        self.setModal(True)
        self.resize(420, 160)
        self.info = info

        layout = QVBoxLayout(self)
        label = QLabel(
            f"发现新版本 <b>{info.tag}</b>（当前 {self.parent_version()}）。\n"
            f"{info.name}\n\n"
            "点击「立即更新」将下载安装包并退出本程序开始安装。"
        )
        label.setTextFormat(Qt.RichText)
        label.setWordWrap(True)
        layout.addWidget(label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.hide()
        layout.addWidget(self.bar)

        buttons = QDialogButtonBox()
        self.update_btn = buttons.addButton("立即更新", QDialogButtonBox.AcceptRole)
        buttons.addButton("取消", QDialogButtonBox.RejectRole)
        self.update_btn.clicked.connect(self._start_update)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._worker: DownloadWorker | None = None
        self._dest: Path | None = None

    def parent_version(self) -> str:
        from core.version import __version__

        return __version__

    def _start_update(self) -> None:
        self.update_btn.setEnabled(False)
        self.bar.show()
        tmp = Path(tempfile.gettempdir()) / "WallpaperConverter" / Path(self.info.download_url).name
        self._dest = tmp
        self._worker = DownloadWorker(self.info.download_url, tmp, self)
        self._worker.progressed.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.bar.setMaximum(100)
            self.bar.setValue(int(done * 100 / total))
        else:
            self.bar.setMaximum(0)

    def _on_done(self, path: str) -> None:
        try:
            if sys.platform == "win32":
                subprocess.Popen([path], shell=False)
            else:  # pragma: no cover - windows-targeted app
                subprocess.Popen(["xdg-open", path])
        except OSError as e:
            QMessageBox.critical(self, "错误", f"无法启动安装程序：{e}")
            self.update_btn.setEnabled(True)
            return
        from PySide6.QtWidgets import QApplication

        QApplication.instance().quit()

    def _on_failed(self, message: str) -> None:
        self.bar.hide()
        self.update_btn.setEnabled(True)
        QMessageBox.warning(self, "下载失败", f"{message}\n\n可打开发布页手动下载：\n{self.info.html_url}")
