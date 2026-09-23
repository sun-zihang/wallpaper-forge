from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from core.updater import UpdateError, fetch_latest_release, is_newer


class ReleaseCheckWorker(QThread):
    finished_ok = Signal(object)  # ReleaseInfo | None (None = already latest)
    failed = Signal(str)

    def __init__(self, current_version: str, parent=None):
        super().__init__(parent)
        self.current_version = current_version

    def run(self) -> None:
        try:
            info = fetch_latest_release()
            if is_newer(info.tag, self.current_version):
                self.finished_ok.emit(info)
            else:
                self.finished_ok.emit(None)
        except UpdateError as e:
            self.failed.emit(str(e))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"检查更新失败：{e}")


class DownloadWorker(QThread):
    progressed = Signal(int, int)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, url: str, dest, parent=None):
        super().__init__(parent)
        self.url = url
        self.dest = dest
        import threading

        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        from core.updater import download_update

        try:
            def cb(done: int, total: int) -> None:
                self.progressed.emit(done, total)

            download_update(
                self.url, self.dest, progress_cb=cb, cancel_event=self._cancel
            )
            self.finished_ok.emit(str(self.dest))
        except UpdateError as e:
            self.failed.emit(str(e))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"下载失败：{e}")


class UpdateService(QObject):
    update_available = Signal(object)  # ReleaseInfo
    no_update = Signal()
    check_failed = Signal(str)

    def __init__(self, current_version: str, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self._check: ReleaseCheckWorker | None = None

    def check_async(self) -> None:
        if self._check and self._check.isRunning():
            return
        self._check = ReleaseCheckWorker(self.current_version, self)
        self._check.finished_ok.connect(self._on_ok)
        self._check.failed.connect(self.check_failed)
        self._check.start()

    def _on_ok(self, info) -> None:
        if info is not None:
            self.update_available.emit(info)
        else:
            self.no_update.emit()
