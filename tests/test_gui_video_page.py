"""VideoPage mode/frame sync, apply_settings, banner, and start_batch guards."""

from __future__ import annotations

from pathlib import Path

import pytest


def _page(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.pages.video_page import VideoPage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)
    return VideoPage()


def test_parse_at_seconds_valid_and_sorted_unique():
    from gui.pages.video_page import parse_at_seconds

    assert parse_at_seconds("10, 2, 2，0.5") == [0.5, 2.0, 10.0]
    assert parse_at_seconds("3") == [3.0]


@pytest.mark.parametrize(
    "text,frag",
    [
        ("", "有效的指定时间点"),
        (",1", "有效的指定时间点"),
        ("1,", "有效的指定时间点"),
        ("abc", "不是有效数字"),
        ("-1", "正数"),
        ("0", "正数"),
        ("inf", "正数"),
        ("nan", "正数"),
    ],
)
def test_parse_at_seconds_rejects(text, frag):
    from gui.pages.video_page import parse_at_seconds

    with pytest.raises(ValueError) as ei:
        parse_at_seconds(text)
    assert frag in str(ei.value)


def test_parse_at_seconds_caps_count():
    from gui.pages.video_page import _MAX_AT_SECONDS, parse_at_seconds

    text = ",".join(str(i) for i in range(1, _MAX_AT_SECONDS + 2))
    with pytest.raises(ValueError, match="最多"):
        parse_at_seconds(text)


def test_sync_mode_and_frame_mode_visibility(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        # default convert
        assert page.mode.currentData() == "convert"
        assert page.fmt.isVisibleTo(page)
        assert not page.gif_fps.isVisibleTo(page)

        page.mode.setCurrentIndex(1)  # gif
        assert page.gif_fps.isVisibleTo(page)
        assert not page.fmt.isVisibleTo(page)

        page.mode.setCurrentIndex(2)  # frames interval
        assert page.every.isVisibleTo(page)
        assert not page.at_seconds_edit.isVisibleTo(page)

        page.frame_mode.setCurrentIndex(1)  # at
        assert page.at_seconds_edit.isVisibleTo(page)
        assert not page.every.isVisibleTo(page)

        page.mode.setCurrentIndex(3)  # trim
        assert page.t_start.isVisibleTo(page)
        assert not page.at_seconds_edit.isVisibleTo(page)
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_apply_settings_clamps_fps_and_fmt(qapp, tmp_path, monkeypatch):
    from gui import settings_store

    page = _page(qapp, tmp_path, monkeypatch)
    try:
        page.apply_settings({"last_video_format": "NOPE", "default_gif_fps": "x"})
        assert page.fmt.currentText() == "MP4"
        assert page.gif_fps.value() == 15

        page.apply_settings({"last_video_format": "WebM", "default_gif_fps": 999})
        assert page.fmt.currentText() == "WebM"
        assert page.gif_fps.value() == 50

        page.apply_settings({"default_gif_fps": 0})
        assert page.gif_fps.value() == 1
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_format_change_persists(qapp, tmp_path, monkeypatch):
    from gui import settings_store

    page = _page(qapp, tmp_path, monkeypatch)
    try:
        page.fmt.setCurrentText("MKV")
        assert settings_store.load_settings()["last_video_format"] == "MKV"
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_set_ffmpeg_ok_toggles_banner_and_start(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        page.set_ffmpeg_ok(False)
        assert page.banner.isVisibleTo(page)
        assert not page.start_btn.isEnabled()
        page.set_ffmpeg_ok(True)
        assert not page.banner.isVisibleTo(page)
        assert page.start_btn.isEnabled()
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_start_batch_without_ffmpeg(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from gui.pages import video_page as mod

    page = _page(qapp, tmp_path, monkeypatch)
    msgs = []
    monkeypatch.setattr(mod, "ffmpeg_available", lambda: False)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda *a, **k: msgs.append(str(a[2] if len(a) > 2 else k))),
    )
    try:
        page.start_batch()
        assert msgs and "无法处理视频" in msgs[0]
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_start_batch_empty_paths(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from gui.pages import video_page as mod

    page = _page(qapp, tmp_path, monkeypatch)
    msgs = []
    monkeypatch.setattr(mod, "ffmpeg_available", lambda: True)
    monkeypatch.setattr(
        QMessageBox,
        "information",
        staticmethod(lambda *a, **k: msgs.append(str(a[2] if len(a) > 2 else k))),
    )
    try:
        page.start_batch()
        assert msgs and "请先添加视频" in msgs[0]
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_convert_mode_submits_task(qapp, tmp_path, monkeypatch):
    from gui.pages import video_page as mod

    page = _page(qapp, tmp_path, monkeypatch)
    try:
        src = tmp_path / "a.mp4"
        src.write_bytes(b"\x00" * 32)
        page.table.add_paths([src])
        page.fmt.setCurrentText("WebM")
        page.keep_audio.setChecked(False)

        submitted = []
        monkeypatch.setattr(mod, "ffmpeg_available", lambda: True)
        monkeypatch.setattr(page, "_submit", lambda b: submitted.append(b))
        monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: True)
        page.start_batch()
        t = submitted[0][0]
        assert t.params["keep_audio"] is False
        assert t.outputs[0].suffix == ".webm"
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_gif_mode_dur_zero_becomes_none(qapp, tmp_path, monkeypatch):
    from gui.pages import video_page as mod

    page = _page(qapp, tmp_path, monkeypatch)
    try:
        src = tmp_path / "a.mp4"
        src.write_bytes(b"\x00" * 32)
        page.table.add_paths([src])
        page.mode.setCurrentIndex(1)
        page.gif_dur.setValue(0)

        submitted = []
        monkeypatch.setattr(mod, "ffmpeg_available", lambda: True)
        monkeypatch.setattr(page, "_submit", lambda b: submitted.append(b))
        monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: True)
        page.start_batch()
        t = submitted[0][0]
        assert t.params["max_duration"] is None
        assert t.outputs[0].suffix == ".gif"
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_trim_rejects_multiple_sources(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from gui.pages import video_page as mod

    page = _page(qapp, tmp_path, monkeypatch)
    msgs = []
    monkeypatch.setattr(mod, "ffmpeg_available", lambda: True)
    monkeypatch.setattr(
        QMessageBox,
        "information",
        staticmethod(lambda *a, **k: msgs.append(str(a[2] if len(a) > 2 else k))),
    )
    try:
        page.mode.setCurrentIndex(3)
        a = tmp_path / "a.mp4"
        b = tmp_path / "b.mp4"
        a.write_bytes(b"\x00" * 8)
        b.write_bytes(b"\x00" * 8)
        page.table.add_paths([a, b])
        page.start_batch()
        assert msgs and "一次请选择一个视频" in msgs[0]
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_trim_single_submits(qapp, tmp_path, monkeypatch):
    from gui.pages import video_page as mod

    page = _page(qapp, tmp_path, monkeypatch)
    try:
        page.mode.setCurrentIndex(3)
        a = tmp_path / "a.mp4"
        a.write_bytes(b"\x00" * 8)
        page.table.add_paths([a])
        submitted = []
        monkeypatch.setattr(mod, "ffmpeg_available", lambda: True)
        monkeypatch.setattr(page, "_submit", lambda b: submitted.append(b))
        monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: True)
        page.start_batch()
        t = submitted[0][0]
        assert t.params["start"] >= 0
        assert t.params["end"] > t.params["start"]
        assert t.outputs[0].suffix == ".mp4"
    finally:
        page.deleteLater()
        qapp.processEvents()
