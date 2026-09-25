"""SettingsPage load/save/ffmpeg refresh pure paths (no modal dialogs)."""

from __future__ import annotations

import json

from core.ffmpeg_finder import FFmpegNotFound


def test_settings_page_about_shows_core_version(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QLabel

    from gui import settings_store
    from gui.pages.settings_page import SettingsPage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    page = SettingsPage()
    try:
        labels = [lb.text() for lb in page.findChildren(QLabel)]
        assert any("Wallpaper Converter" in t for t in labels)
        from core.version import __version__

        assert any(__version__ in t for t in labels)
        assert page.quality.value() >= 1
        assert page.gif_fps.value() >= 1
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_settings_page_save_writes_selected_values(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.pages.settings_page import SettingsPage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    changed = []
    page = SettingsPage(on_changed=lambda: changed.append(1))
    try:
        page.mode.setCurrentIndex(1)
        page.quality.setValue(77)
        page.gif_fps.setValue(24)
        page.auto_check.setChecked(False)
        page._save()
        assert changed == [1]
        s = settings_store.load_settings()
        assert s["output_mode"] == "unified"
        assert s["default_quality"] == 77
        assert s["default_gif_fps"] == 24
        assert s["auto_check_update"] is False
        assert s["unified_dir"] == ""
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_settings_page_refresh_ffmpeg_found(qapp, tmp_path, monkeypatch):
    from pathlib import Path

    from gui import settings_store
    from gui.pages import settings_page as mod

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    monkeypatch.setattr(mod, "find_ffmpeg", lambda: Path("C:/ffmpeg/bin/ffmpeg.exe"))
    page = mod.SettingsPage()
    try:
        page.refresh_ffmpeg()
        assert "已找到" in page.ff_label.text()
        assert "ffmpeg.exe" in page.ff_label.text()
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_settings_page_refresh_ffmpeg_missing(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.pages import settings_page as mod

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    def boom():
        raise FFmpegNotFound("nope")

    monkeypatch.setattr(mod, "find_ffmpeg", boom)
    page = mod.SettingsPage()
    try:
        page.refresh_ffmpeg()
        assert "未找到 ffmpeg" in page.ff_label.text()
        # recheck also refreshes and notifies
        calls = []
        page._on_changed = lambda: calls.append(1)
        page._recheck()
        assert calls == [1]
        assert "未找到" in page.ff_label.text()
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_settings_page_loads_unified_dir_from_settings(qapp, tmp_path, monkeypatch):
    from gui import settings_store

    settings_path = tmp_path / "settings.json"
    out_dir = tmp_path / "unified-out"
    settings_path.write_text(
        json.dumps(
            {"output_mode": "unified", "unified_dir": str(out_dir)},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    from gui.pages.settings_page import SettingsPage

    page = SettingsPage()
    try:
        assert page.mode.currentData() == "unified"
        assert page._unified_dir == out_dir
        assert str(out_dir) in page.dir_label.text()
    finally:
        page.deleteLater()
        qapp.processEvents()
