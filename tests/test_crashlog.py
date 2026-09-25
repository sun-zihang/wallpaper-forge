"""Crash log writing and excepthook install (no real crash dialogs)."""

from __future__ import annotations

import sys
from pathlib import Path


def test_write_crash_log_creates_dirs_and_content(tmp_path: Path):
    from gui.crashlog import write_crash_log

    try:
        raise RuntimeError("boom-message")
    except RuntimeError as exc:
        path = write_crash_log(exc, tmp_path)
    assert path == tmp_path / "logs" / "last_error.log"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "RuntimeError" in text
    assert "boom-message" in text


def test_install_crash_handler_writes_log_and_shows_dialog(qapp, tmp_path, monkeypatch):
    from gui import crashlog as mod
    from gui.crashlog import install_crash_handler

    monkeypatch.setattr(mod, "settings_dir", lambda: tmp_path)
    criticals = []
    monkeypatch.setattr(
        mod.QMessageBox,
        "critical",
        staticmethod(lambda *a, **k: criticals.append(a)),
    )
    old = sys.excepthook
    try:
        install_crash_handler()
        assert sys.excepthook is not old
        # simulate uncaught
        try:
            raise ValueError("uncaught-test")
        except ValueError:
            exc_info = sys.exc_info()
        sys.excepthook(*exc_info)
        log = tmp_path / "logs" / "last_error.log"
        assert log.is_file()
        assert "uncaught-test" in log.read_text(encoding="utf-8")
        assert criticals, "should show critical dialog when QApplication exists"
        assert "程序发生错误" in str(criticals[0][2]) or "日志路径" in str(
            criticals[0][2] if len(criticals[0]) > 2 else criticals[0]
        )
    finally:
        sys.excepthook = old


def test_install_crash_handler_survives_write_failure(qapp, monkeypatch, tmp_path):
    from gui import crashlog as mod
    from gui.crashlog import install_crash_handler

    def boom(_exc):
        raise OSError("disk full")

    monkeypatch.setattr(mod, "write_crash_log", boom)
    monkeypatch.setattr(mod, "settings_dir", lambda: tmp_path / "settings")
    criticals = []
    monkeypatch.setattr(
        mod.QMessageBox,
        "critical",
        staticmethod(lambda *a, **k: criticals.append(a)),
    )
    old = sys.excepthook
    try:
        install_crash_handler()
        try:
            raise RuntimeError("second")
        except RuntimeError:
            info = sys.exc_info()
        sys.excepthook(*info)  # must not raise
        # falls back to expected path under settings_dir
        assert (tmp_path / "settings" / "logs" / "last_error.log").is_file() or criticals
    finally:
        sys.excepthook = old


def test_write_crash_log_accepts_non_exception_context(tmp_path: Path):
    from gui.crashlog import write_crash_log

    class E(Exception):
        pass

    e = E("custom")
    path = write_crash_log(e, tmp_path / "nested" / "base")
    assert path.is_file()
    assert "custom" in path.read_text(encoding="utf-8")


def test_excepthook_falls_back_to_appdata_path(qapp, monkeypatch):
    from gui import crashlog as mod
    from gui.crashlog import install_crash_handler

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(mod, "write_crash_log", boom)
    monkeypatch.setattr(mod, "_expected_log_path", boom)
    criticals = []
    monkeypatch.setattr(
        mod.QMessageBox,
        "critical",
        staticmethod(lambda *a, **k: criticals.append(a)),
    )
    old = sys.excepthook
    try:
        install_crash_handler()
        try:
            raise ValueError("fallback-one")
        except ValueError:
            info = sys.exc_info()
        sys.excepthook(*info)  # must not raise
        assert criticals
        shown = criticals[0][2]
        assert "WallpaperConverter" in shown
        assert "last_error.log" in shown
    finally:
        sys.excepthook = old


def test_excepthook_final_fallback_when_home_unavailable(qapp, monkeypatch):
    from gui import crashlog as mod
    from gui.crashlog import install_crash_handler

    def boom(*_a, **_k):
        raise OSError("nope")

    def no_home():
        raise OSError("home unavailable")

    monkeypatch.setattr(mod, "write_crash_log", boom)
    monkeypatch.setattr(mod, "_expected_log_path", boom)
    monkeypatch.setattr(mod.Path, "home", staticmethod(no_home))
    criticals = []
    monkeypatch.setattr(
        mod.QMessageBox,
        "critical",
        staticmethod(lambda *a, **k: criticals.append(a)),
    )
    old = sys.excepthook
    try:
        install_crash_handler()
        try:
            raise ValueError("fallback-two")
        except ValueError:
            info = sys.exc_info()
        sys.excepthook(*info)  # must not raise
        assert criticals
        shown = criticals[0][2]
        assert "last_error.log" in shown
        assert "WallpaperConverter" not in shown  # home branch skipped
    finally:
        sys.excepthook = old


def test_excepthook_swallows_dialog_failure(qapp, tmp_path, monkeypatch):
    from gui import crashlog as mod
    from gui.crashlog import install_crash_handler

    def bad_dialog(*_a, **_k):
        raise RuntimeError("dialog backend down")

    monkeypatch.setattr(mod, "settings_dir", lambda: tmp_path)
    monkeypatch.setattr(mod.QMessageBox, "critical", staticmethod(bad_dialog))
    old = sys.excepthook
    try:
        install_crash_handler()
        try:
            raise ValueError("dialog-crash")
        except ValueError:
            info = sys.exc_info()
        sys.excepthook(*info)  # must not raise despite dialog failure
    finally:
        sys.excepthook = old
