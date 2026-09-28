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


def test_video_edit_page_integrated_in_main_window(qapp, tmp_path, monkeypatch):
    from gui.main_window import MainWindow

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("gui.settings_store._settings_path", lambda: settings_path)
    win = MainWindow("test")
    try:
        nav_labels = [win.nav.item(i).text() for i in range(win.nav.count())]
        assert "视频编辑" in nav_labels
        assert win.video_edit_page is not None
        assert win.video_edit_page in win._processing_pages()
        assert win.stack.indexOf(win.video_edit_page) >= 0
    finally:
        win.deleteLater()
        qapp.processEvents()


# ---- 渲染 / 鼠标交互 / 导出链路 / 参数发射路径（覆盖率补齐轮） ----


def _page_with_clip(qapp, tmp_path, monkeypatch, duration=4.0):
    page = _page(qapp, tmp_path, monkeypatch)
    _enable_ffmpeg(page, monkeypatch)
    src = _add_video(page, tmp_path)
    monkeypatch.setattr("gui.pages.video_edit_page.probe_video_duration", lambda p: duration)
    page._add_selected_to_timeline()
    return page, src


def test_timeline_canvas_paints_ruler_lanes_playhead(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QPointF

    from gui.video_edit.timeline_widget import format_time

    page, _src = _page_with_clip(qapp, tmp_path, monkeypatch)
    try:
        canvas = page.timeline.canvas
        canvas.resize_for_content()
        assert not canvas.grab().isNull(), "paintEvent 渲染成功"
        assert canvas._tick_step() in (0.5, 1, 2, 5, 10, 15, 30, 60, 120)
        assert format_time(-3) == "00:00.0"
        assert format_time(65.25) == "01:05.2"
        # 播放头移动后重绘仍成功
        page.timeline.set_playhead_sec(1.0)
        assert not canvas.grab().isNull()
        assert QPointF(0, 0) is not None
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_timeline_mouse_select_drag_and_double_click_split(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QPointF

    page, _src = _page_with_clip(qapp, tmp_path, monkeypatch)
    try:
        widget = page.timeline
        track0_y = 26 + 26  # RULER_HEIGHT + 半轨
        # 在片段(0..4s, x=0..240)上按下 → 选中并驱动参数面板
        widget.handle_mouse_press(QPointF(120, track0_y))
        assert page.timeline.selected_clip_id is not None
        assert page.params_panel._clip is not None
        # 标尺区域按下 → 进入播放头拖拽
        widget.handle_mouse_press(QPointF(60, 10))
        assert page.timeline.playhead_sec == 1.0
        widget.handle_mouse_move(QPointF(180, 10))
        assert page.timeline.playhead_sec == 3.0
        widget.handle_mouse_release(QPointF(180, 10))
        # 双击片段 → 按播放头位置拆分（3.0s 落在 0..4s 内）
        widget.handle_mouse_double_click(QPointF(120, track0_y))
        assert len(page._timeline.tracks[0].clips) == 2
        # 空白处按下 → 取消选中
        widget.handle_mouse_press(QPointF(420, track0_y))
        assert page.timeline.selected_clip_id is None
        # 越界轨道索引的点击是无害 no-op
        widget.handle_mouse_press(QPointF(120, 5000))
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_params_panel_crop_and_overlay_emit_paths(qapp):
    from gui.video_edit.model import Clip
    from gui.video_edit.params_panel import ParamsPanel

    panel = ParamsPanel()
    try:
        clip = Clip(id="c1", source_file="a.mp4", timeline_in=0, source_in=0, source_out=5)
        emitted = []
        panel.params_changed.connect(lambda cid, partial: emitted.append((cid, partial)))
        panel.show_for_clip(clip)

        panel.crop_check.setChecked(True)
        assert emitted[-1][1]["transform"]["crop"] is not None
        panel.crop_check.setChecked(False)
        assert emitted[-1][1]["transform"]["crop"] is None

        panel.overlay_check.setChecked(True)
        assert emitted[-1][1]["overlay"]["text"] == "文字"
        panel.overlay_text.setText("你好")
        assert emitted[-1][1]["overlay"]["text"] == "你好"
        panel.overlay_x_slider.setValue(30)
        assert emitted[-1][1]["overlay"]["position"]["x"] == 30
        panel.overlay_y_slider.setValue(70)
        assert emitted[-1][1]["overlay"]["position"]["y"] == 70
        panel.opacity_slider.setValue(40)
        assert emitted[-1][1]["overlay"]["opacity"] == 0.4
        panel.overlay_check.setChecked(False)
        assert emitted[-1][1]["overlay"] is None

        # 未选中片段时所有发射都被吞掉
        panel.show_for_clip(None)
        before = len(emitted)
        panel.overlay_check.setChecked(True)
        assert len(emitted) == before
    finally:
        panel.deleteLater()
        qapp.processEvents()


def test_params_panel_refresh_roundtrip_with_overlay(qapp):
    from gui.video_edit.model import Clip, create_default_params
    from gui.video_edit.params_panel import ParamsPanel

    panel = ParamsPanel()
    try:
        params = create_default_params()
        params["overlay"] = {
            "type": "text",
            "text": "水印文字",
            "fontSize": 32,
            "fontColor": "#ff0000",
            "opacity": 0.5,
            "position": {"x": 20, "y": 80},
        }
        params["transform"]["crop"] = {"x": 1, "y": 2, "width": 3, "height": 4}
        clip = Clip(
            id="c2",
            source_file="a.mp4",
            timeline_in=0,
            source_in=0,
            source_out=5,
            params=params,
        )
        panel.show_for_clip(clip)
        assert panel.overlay_text.text() == "水印文字"
        assert panel.overlay_font_size.value() == 32
        assert panel.overlay_x_slider.value() == 20
        assert panel.overlay_y_slider.value() == 80
        assert panel.opacity_slider.value() == 50
        assert panel.crop_x.value() == 1 and panel.crop_w.value() == 3
        assert panel.speed_spin.value() == 1.0
        assert panel.volume_slider.value() == 100
    finally:
        panel.deleteLater()
        qapp.processEvents()


def test_export_dialog_settings_progress_and_browse(qapp, monkeypatch):
    from gui.pages.video_edit_page import _ExportDialog

    dlg = _ExportDialog("C:/out/a_edited.mp4")
    try:
        s = dlg.settings()
        assert s == {"format": "mp4", "video_codec": "libx264", "crf": 23, "preset": "veryfast"}
        dlg.set_progress(40, "阶段一")
        assert dlg.progress_bar.value() == 40
        assert dlg.progress_label.text() == "阶段一"
        dlg.set_progress(-1, "只改文案")
        assert dlg.progress_bar.value() == 40

        collected = []
        dlg.start_requested.connect(collected.append)
        dlg.go_btn.click()
        assert collected == [s]
        dlg.disable_start()
        assert not dlg.go_btn.isEnabled()

        class _FakeFD:
            @staticmethod
            def getSaveFileName(*a, **k):
                return ("C:/out/final.mp4", "")

        monkeypatch.setattr("gui.pages.video_edit_page.QFileDialog", _FakeFD)
        dlg.browse_btn.setEnabled(True)  # disable_start 会连 browse 一起禁用
        dlg.browse_btn.click()
        assert dlg.output_path == "C:/out/final.mp4"
        assert dlg.name_edit.text() == "C:/out/final.mp4"
    finally:
        dlg.deleteLater()
        qapp.processEvents()


def test_export_thread_success_failure_and_cancel(qapp):
    from gui.pages.video_edit_page import _ExportThread

    class OkExporter:
        def export(self, timeline, settings, on_progress=None, cancel_event=None):
            if on_progress:
                on_progress(50, "half")
            return b"video-bytes"

    class BadExporter:
        def export(self, timeline, settings, on_progress=None, cancel_event=None):
            raise RuntimeError("boom")

    done, fails = [], []
    t1 = _ExportThread(OkExporter(), None, {})
    t1.finished.connect(done.append)
    t1.run()
    assert done == [b"video-bytes"]

    t2 = _ExportThread(BadExporter(), None, {})
    t2.failed.connect(fails.append)
    t2.run()
    assert len(fails) == 1 and "boom" in fails[0]

    t3 = _ExportThread(OkExporter(), None, {})
    t3.cancel()
    assert t3._cancel.is_set()


def test_page_export_flow_writes_output(qapp, tmp_path, monkeypatch):
    from pathlib import Path

    page, _src = _page_with_clip(qapp, tmp_path, monkeypatch)
    try:
        warned = []
        monkeypatch.setattr(
            "gui.pages.video_edit_page.QMessageBox.warning", lambda *a, **k: warned.append(a)
        )
        informed = []
        monkeypatch.setattr(
            "gui.pages.video_edit_page.QMessageBox.information",
            lambda *a, **k: informed.append(a),
        )

        class FakeExporter:
            def export(self, timeline, settings, on_progress=None, cancel_event=None):
                assert settings["format"] == "mp4"
                return b"fake-video"

        monkeypatch.setattr(page, "_exporter", FakeExporter())
        # 线程同步执行，测试确定性
        monkeypatch.setattr(
            "gui.pages.video_edit_page._ExportThread.start", lambda self: self.run()
        )
        page._open_export_dialog()
        dlg = page._export_dialog
        assert dlg is not None
        dlg.go_btn.click()
        qapp.processEvents()
        out = Path(dlg.output_path)
        assert out.read_bytes() == b"fake-video"
        assert out.name == "a_edited.mp4"
        assert informed, "导出完成提示已弹出"
        assert not warned
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_page_export_guards_and_failure_paths(qapp, tmp_path, monkeypatch):

    page = _page(qapp, tmp_path, monkeypatch)
    try:
        warned = []
        informed = []
        monkeypatch.setattr(
            "gui.pages.video_edit_page.QMessageBox.warning", lambda *a, **k: warned.append(a)
        )
        monkeypatch.setattr(
            "gui.pages.video_edit_page.QMessageBox.information",
            lambda *a, **k: informed.append(a),
        )

        # 无片段时打开导出 → 提示
        page._open_export_dialog()
        assert informed, "时间线上没有片段提示"

        # 有片段但 ffmpeg 不可用 → 警告
        from gui.video_edit.model import Clip

        clip = Clip(
            id="c1", source_file=str(tmp_path / "a.mp4"), timeline_in=0, source_in=0, source_out=4
        )
        page._timeline.tracks.append(
            type("T", (), {"clips": [clip], "type": "video", "muted": False})()
        )
        page._ffmpeg_ok = False
        page._open_export_dialog()
        assert warned and warned[-1][2] == "未找到 ffmpeg，无法导出视频"
        warned.clear()

        # 无对话框时 _run_export 是 no-op
        page._export_dialog = None
        page._ffmpeg_ok = True
        page._run_export({})
        # 失败路径弹警告并收对话框
        page._export_failed("导出炸了")
        assert warned[-1][2] == "导出炸了"
        # 取消导出：线程在跑则 cancel
        cancelled = []

        class FakeThread:
            def isRunning(self):
                return True

            def cancel(self):
                cancelled.append(1)

            def wait(self, ms):
                return True

        page._export_thread = FakeThread()
        page._cancel_export()
        assert cancelled
        # start_batch 是 no-op（导出走自己的对话框）
        page.start_batch()
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_default_export_path_fallbacks(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        # 无片段、无 last_dir → 相对名
        assert page._default_export_path() == "output.mp4"
        page._settings["last_dir"] = str(tmp_path)
        assert page._default_export_path() == str(tmp_path / "output.mp4")
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_player_position_guard_and_seek(qapp, tmp_path, monkeypatch):
    page, _src = _page_with_clip(qapp, tmp_path, monkeypatch)
    try:
        # 拖动播放头引起的 seek 期间，播放器回报被忽略（防回环）
        page._seeking = True
        page._on_player_position(5000)
        assert page.timeline.playhead_sec == 0
        page._seeking = False
        page._on_player_position(5000)
        assert page.timeline.playhead_sec == 5.0
        assert page.time_label.text() == "00:05.0"
    finally:
        page.deleteLater()
        qapp.processEvents()
