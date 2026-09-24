from __future__ import annotations

import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from gui.settings_store import settings_dir


def write_crash_log(exc: BaseException, base_dir: Path) -> Path:
    path = Path(base_dir) / "logs" / "last_error.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    path.write_text(text, encoding="utf-8")
    return path


def _expected_log_path() -> Path:
    return Path(settings_dir()) / "logs" / "last_error.log"


def install_crash_handler() -> None:
    def excepthook(exc_type, exc_value, exc_traceback) -> None:
        try:
            log_path = write_crash_log(exc_value, settings_dir())
        except BaseException:
            try:
                log_path = _expected_log_path()
            except BaseException:
                try:
                    log_path = (
                        Path.home()
                        / "AppData"
                        / "Roaming"
                        / "WallpaperConverter"
                        / "logs"
                        / "last_error.log"
                    )
                except BaseException:
                    log_path = Path("logs") / "last_error.log"
        try:
            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None,
                    "程序发生错误",
                    f"程序遇到未处理的错误，日志路径：\n{log_path}",
                )
        except BaseException:
            pass

    sys.excepthook = excepthook
