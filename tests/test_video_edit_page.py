"""VideoEditPage skeleton, wiring, timeline interactions, and export guards."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox


def _page(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.pages.video_edit_page import VideoEditPage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)
    return VideoEditPage()


def _add_video(page, tmp_path, name: str = "a.mp4"):
    from pathlib import Path

    src = Path(tmp_path) / name
    src.write_bytes(b"\x00" * 32)
    page.table.add_paths([src])
    return src


def _enable_ffmpeg(page, monkeypatch):
    monkeypatch.setattr(page, "_ffmpeg_ok", True)


def test_page_skeleton(qapp, tmp_path, monkeypatch):
    from gui.video_edit.params_panel import ParamsPanel
    from gui.video_edit.preview_widget import PreviewWidget
    from gui.video_edit.timeline_widget import TimelineWidget

    page = _page(qapp, tmp_path, monkeypatch)
    try:
        assert isinstance(page.preview, PreviewWidget)
        assert isinstance(page.timeline, TimelineWidget)
        assert isinstance(page.params_panel, ParamsPanel)
        assert page.timeline.timeline is page._timeline
        assert page.undo_btn is not None and page.redo_btn is not None
        assert page.export_btn is not None and page.add_to_timeline_btn is not None
        assert page.table.table.rowCount() == 0
        assert page.timeline.playhead_ms == 0
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_apply_settings_tolerates_empty(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        page.apply_settings({})
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_add_files_then_add_to_timeline(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        _enable_ffmpeg(page, monkeypatch)
        _add_video(page, tmp_path)
        assert page.table.table.rowCount() == 1
        page.add_to_timeline_btn.click()
        tracks = page._timeline.tracks
        assert len(tracks) == 1
        assert tracks[0].type == "video"
        assert len(tracks[0].clips) == 1
        assert page._timeline.duration == pytest.approx(10.0)
        clip = tracks[0].clips[0]
        assert page.timeline.selected_clip_id == clip.id
        assert page.params_panel.scroll_area.isVisibleTo(page)
        assert not page.params_panel.empty_label.isVisibleTo(page)
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_add_to_timeline_without_files_warns(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    _enable_ffmpeg(page, monkeypatch)
    msgs = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        staticmethod(lambda *a, **k: msgs.append(str(a[2] if len(a) > 2 else k))),
    )
    try:
        page.add_to_timeline_btn.click()
        assert msgs and "请先添加视频文件" in msgs[0]
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_select_clip_emits_signal_and_shows_params(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        _enable_ffmpeg(page, monkeypatch)
        _add_video(page, tmp_path)
        page.add_to_timeline_btn.click()
        clip = page._timeline.tracks[0].clips[0]

        selected = []
        page.timeline.clip_selected.connect(lambda cid: selected.append(cid))
        page.timeline.select_clip(clip.id)
        assert selected == [clip.id]
        assert page.params_panel._clip is clip

        page.timeline.select_clip(None)
        assert page.timeline.selected_clip_id is None
        assert page.params_panel.empty_label.isVisibleTo(page)
        assert not page.params_panel.scroll_area.isVisibleTo(page)
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_params_change_runs_through_engine_and_undo_redo(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        _enable_ffmpeg(page, monkeypatch)
        _add_video(page, tmp_path)
        page.add_to_timeline_btn.click()
        clip = page._timeline.tracks[0].clips[0]

        page.params_panel.speed_spin.setValue(2.0)
        assert clip.speed == pytest.approx(2.0)
        assert page.undo_btn.isEnabled()

        page.undo_btn.click()
        assert clip.speed == pytest.approx(1.0)
        assert page.redo_btn.isEnabled()

        page.redo_btn.click()
        assert clip.speed == pytest.approx(2.0)

        page.params_panel.flip_h_check.setChecked(True)
        assert clip.params["transform"]["flip_h"] is True
        page.undo_btn.click()
        assert clip.params["transform"]["flip_h"] is False
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_split_clip_via_command_and_undo(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        _enable_ffmpeg(page, monkeypatch)
        _add_video(page, tmp_path)
        page.add_to_timeline_btn.click()
        track = page._timeline.tracks[0]
        clip = track.clips[0]

        page.timeline.clip_split_requested.emit(clip.id, 5.0)
        assert len(track.clips) == 2
        assert track.clips[0].duration == pytest.approx(5.0)
        assert track.clips[1].timeline_in == pytest.approx(5.0)

        page.undo_btn.click()
        assert len(track.clips) == 1

        page.redo_btn.click()
        assert len(track.clips) == 2
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_track_add_remove_and_mute(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        page.timeline.add_video_btn.click()
        page.timeline.add_video_btn.click()
        assert len(page._timeline.tracks) == 2

        track = page._timeline.tracks[0]
        page.timeline.toggle_mute(track.id)
        assert track.muted is True

        page.timeline.remove_track(track.id)
        assert len(page._timeline.tracks) == 1

        page.timeline.add_audio_btn.click()
        assert page._timeline.tracks[-1].type == "audio"
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_playhead_moves_signal_and_label(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        moved = []
        page.timeline.playhead_moved.connect(lambda ms: moved.append(ms))
        page.timeline.set_playhead_ms(2000)
        assert moved == [2000]
        assert page.timeline.playhead_ms == 2000
        assert page.time_label.text() == "00:02.0"
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_export_without_clips_warns(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    msgs = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        staticmethod(lambda *a, **k: msgs.append(str(a[2] if len(a) > 2 else k))),
    )
    try:
        page.export_btn.click()
        assert msgs and "没有片段" in msgs[0]
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_export_dialog_opens_settings_and_cancel(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QObject, Signal

    import gui.pages.video_edit_page as mod

    class _FakeThread(QObject):
        progress = Signal(int, str)
        finished = Signal(bytes)
        failed = Signal(str)

        def __init__(self, exporter, timeline, settings):
            super().__init__()
            self._settings = settings

        def start(self):
            pass

    monkeypatch.setattr(mod, "_ExportThread", _FakeThread)

    page = _page(qapp, tmp_path, monkeypatch)
    try:
        _enable_ffmpeg(page, monkeypatch)
        _add_video(page, tmp_path)
        page.add_to_timeline_btn.click()

        page.export_btn.click()
        dialog = page._export_dialog
        assert isinstance(dialog, mod._ExportDialog)
        assert page.export_btn.isEnabled()

        settings = {}
        dialog.start_requested.connect(lambda s: settings.update(s))
        dialog.go_btn.click()
        assert settings["format"] == "mp4"
        assert settings["video_codec"] == "libx264"
        assert settings["crf"] == 23
        assert settings["preset"] == "veryfast"
        assert not dialog.go_btn.isEnabled()

        dialog.set_progress(50, "正在导出…")
        assert dialog.progress_bar.value() == 50

        page._export_dialog = None
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_export_default_path_uses_first_clip(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        _enable_ffmpeg(page, monkeypatch)
        _add_video(page, tmp_path, "clip_a.mp4")
        page.add_to_timeline_btn.click()
        assert page._default_export_path().endswith("clip_a_edited.mp4")
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_set_ffmpeg_ok_toggles_banner_and_buttons(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        page.set_ffmpeg_ok(False)
        assert page.banner.isVisibleTo(page)
        assert not page.export_btn.isEnabled()
        assert not page.add_to_timeline_btn.isEnabled()
        page.set_ffmpeg_ok(True)
        assert not page.banner.isVisibleTo(page)
        assert page.export_btn.isEnabled()
        assert page.add_to_timeline_btn.isEnabled()
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_play_toggle_changes_label(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        page.play_btn.setChecked(True)
        assert page.play_btn.text() == "暂停"
        page.play_btn.setChecked(False)
        assert page.play_btn.text() == "播放"
    finally:
        page.deleteLater()
        qapp.processEvents()
