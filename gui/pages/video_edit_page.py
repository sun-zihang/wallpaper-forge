from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.ffmpeg_finder import ffmpeg_available
from core.video_ops import probe_video_duration
from gui.pages.base import BasePage
from gui.video_edit.engine import AdjustParamsCommand, EditEngine, SplitClipCommand
from gui.video_edit.exporter import NativeExporter
from gui.video_edit.model import Clip, TimelineModel
from gui.video_edit.params_panel import ParamsPanel
from gui.video_edit.preview_widget import PreviewWidget
from gui.video_edit.timeline_widget import TimelineWidget, format_time
from gui.workers import friendly_error

_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv"}
_DEFAULT_CLIP_SEC = 10.0
_FORMATS = [("MP4", "mp4"), ("WebM", "webm")]
_CODECS = [
    ("H.264 (libx264)", "libx264"),
    ("H.265 (libx265)", "libx265"),
    ("VP9 (libvpx-vp9)", "libvpx-vp9"),
]
_PRESETS = [
    ("ultrafast", "ultrafast"),
    ("superfast", "superfast"),
    ("veryfast", "veryfast"),
    ("faster", "faster"),
    ("fast", "fast"),
    ("medium", "medium"),
    ("slow", "slow"),
    ("slower", "slower"),
]


class _ExportThread(QThread):
    progress = Signal(int, str)
    finished = Signal(bytes)
    failed = Signal(str)

    def __init__(self, exporter, timeline, settings: dict) -> None:
        super().__init__()
        self._exporter = exporter
        self._timeline = timeline
        self._settings = settings
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            data = self._exporter.export(
                self._timeline,
                self._settings,
                on_progress=lambda pct, msg: self.progress.emit(pct, msg),
                cancel_event=self._cancel,
            )
        except Exception as e:
            self.failed.emit(friendly_error(e))
            return
        self.finished.emit(data)


class _ExportDialog(QDialog):
    start_requested = Signal(dict)
    cancel_requested = Signal()

    def __init__(self, default_path: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("导出设置")
        self.setMinimumWidth(460)
        self.output_path = default_path

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        row = QHBoxLayout()
        row.addWidget(QLabel("格式："))
        self.fmt_combo = QComboBox()
        for text, data in _FORMATS:
            self.fmt_combo.addItem(text, data)
        row.addWidget(self.fmt_combo, 1)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("编码器："))
        self.codec_combo = QComboBox()
        for text, data in _CODECS:
            self.codec_combo.addItem(text, data)
        row.addWidget(self.codec_combo, 1)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("质量(CRF)："))
        self.crf_slider = QSlider(Qt.Orientation.Horizontal)
        self.crf_slider.setRange(0, 51)
        self.crf_slider.setValue(23)
        self.crf_label = QLabel("23")
        self.crf_label.setFixedWidth(36)
        self.crf_label.setObjectName("pathText")
        row.addWidget(self.crf_slider, 1)
        row.addWidget(self.crf_label)
        layout.addLayout(row)
        self.crf_slider.valueChanged.connect(lambda v: self.crf_label.setText(str(v)))

        row = QHBoxLayout()
        row.addWidget(QLabel("预设："))
        self.preset_combo = QComboBox()
        for text, data in _PRESETS:
            self.preset_combo.addItem(text, data)
        self.preset_combo.setCurrentText("veryfast")
        row.addWidget(self.preset_combo, 1)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("文件名："))
        self.name_edit = QLineEdit(self.output_path)
        row.addWidget(self.name_edit, 1)
        self.browse_btn = QPushButton("浏览…")
        self.browse_btn.setObjectName("secondary")
        row.addWidget(self.browse_btn)
        layout.addLayout(row)
        self.browse_btn.clicked.connect(self._browse)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.progress_label = QLabel("")
        self.progress_label.setObjectName("mutedText")
        layout.addWidget(self.progress_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("secondary")
        self.go_btn = QPushButton("开始导出")
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.go_btn)
        layout.addLayout(buttons)

        self.cancel_btn.clicked.connect(self.cancel_requested)
        self.cancel_btn.clicked.connect(self.reject)
        self.go_btn.clicked.connect(lambda: self.start_requested.emit(self.settings()))

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "选择输出文件", self.output_path, "视频文件 (*.mp4 *.webm)"
        )
        if path:
            self.output_path = path
            self.name_edit.setText(path)

    def settings(self) -> dict:
        return {
            "format": self.fmt_combo.currentData(),
            "video_codec": self.codec_combo.currentData(),
            "crf": self.crf_slider.value(),
            "preset": self.preset_combo.currentData(),
        }

    def set_progress(self, pct: int, msg: str) -> None:
        if pct >= 0:
            self.progress_bar.setValue(pct)
        if msg:
            self.progress_label.setText(msg)

    def disable_start(self) -> None:
        self.go_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)


class VideoEditPage(BasePage):
    def __init__(self) -> None:
        super().__init__(_VIDEO_EXTS)
        self._timeline = TimelineModel(id="")
        self._engine = EditEngine(self._timeline)
        self._exporter = NativeExporter()
        self._ffmpeg_ok: bool | None = None
        self._export_thread: _ExportThread | None = None
        self._export_dialog: _ExportDialog | None = None
        self._seeking = False

        self.banner = QLabel(
            "未检测到 ffmpeg，无法添加片段或导出视频。请安装 ffmpeg 或设置 WALLPAPER_FORGE_FFMPEG。"
        )
        self.banner.setObjectName("banner")
        self.banner.hide()

        self.add_files_btn = QPushButton("添加文件")
        self.add_files_btn.clicked.connect(self._add_files)
        self.add_to_timeline_btn = QPushButton("添加到时间线")
        self.add_to_timeline_btn.clicked.connect(self._add_selected_to_timeline)

        left_box = QGroupBox("文件库")
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(6)
        left_layout.addWidget(self.add_files_btn)
        left_layout.addWidget(self.add_to_timeline_btn)
        left_layout.addWidget(self.table, 1)

        self.preview = PreviewWidget()
        self.play_btn = QPushButton("播放")
        self.play_btn.setCheckable(True)
        self.time_label = QLabel(format_time(0))
        self.time_label.setObjectName("pathText")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.valueChanged.connect(lambda v: self.preview.set_volume(v / 100))

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.time_label)
        controls.addStretch(1)
        controls.addWidget(QLabel("音量："))
        controls.addWidget(self.volume_slider)

        self.timeline = TimelineWidget(self._timeline)
        self.undo_btn = QPushButton("撤销")
        self.redo_btn = QPushButton("重做")
        self.export_btn = QPushButton("导出视频")
        edit_row = QHBoxLayout()
        edit_row.addWidget(self.undo_btn)
        edit_row.addWidget(self.redo_btn)
        edit_row.addStretch(1)
        edit_row.addWidget(self.export_btn)

        mid = QWidget()
        mid_layout = QVBoxLayout(mid)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(6)
        mid_layout.addWidget(self.preview, 1)
        mid_layout.addLayout(controls)
        mid_layout.addWidget(self.timeline, 1)
        mid_layout.addLayout(edit_row)

        self.params_panel = ParamsPanel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_box)
        splitter.addWidget(mid)
        splitter.addWidget(self.params_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        self.root.addWidget(self.banner)
        self.root.addWidget(splitter, 1)
        self.progress.hide()

        self.play_btn.toggled.connect(self._toggle_play)
        self.timeline.playhead_moved.connect(self._seek_preview)
        self.timeline.playhead_moved.connect(self._sync_time_label)
        self.timeline.selection_cleared.connect(lambda: self.params_panel.show_for_clip(None))
        self.preview.get_player().positionChanged.connect(self._on_player_position)
        self.timeline.clip_selected.connect(self._on_clip_selected)
        self.timeline.clip_split_requested.connect(self._split_clip)
        self.params_panel.params_changed.connect(self._adjust_params)
        self.undo_btn.clicked.connect(self._undo)
        self.redo_btn.clicked.connect(self._redo)
        self.export_btn.clicked.connect(self._open_export_dialog)
        self._sync_edit_buttons()

    def start_batch(self) -> None:
        pass

    def set_ffmpeg_ok(self, ok: bool) -> None:
        self._ffmpeg_ok = bool(ok)
        self.banner.setVisible(not self._ffmpeg_ok)
        self.export_btn.setEnabled(self._ffmpeg_ok)
        self.add_to_timeline_btn.setEnabled(self._ffmpeg_ok)

    def apply_settings(self, settings: dict) -> None:
        super().apply_settings(settings)

    def _check_ffmpeg(self) -> bool:
        if self._ffmpeg_ok is None:
            self._ffmpeg_ok = ffmpeg_available()
        return self._ffmpeg_ok

    def _toggle_play(self, checked: bool) -> None:
        if checked:
            self.preview.play()
            self.play_btn.setText("暂停")
        else:
            self.preview.pause()
            self.play_btn.setText("播放")

    def _sync_time_label(self, position_ms: int) -> None:
        self.time_label.setText(format_time(position_ms / 1000))

    def _seek_preview(self, position_ms: int) -> None:
        self._seeking = True
        try:
            self.preview.seek(position_ms)
        finally:
            QTimer.singleShot(120, self._clear_seeking)

    def _clear_seeking(self) -> None:
        self._seeking = False

    def _on_player_position(self, position_ms: int) -> None:
        if self._seeking:
            return
        self.timeline.set_playhead_ms(position_ms)

    def _add_selected_to_timeline(self) -> None:
        if not self._check_ffmpeg():
            QMessageBox.warning(self, "提示", "未找到 ffmpeg，无法读取视频时长")
            return
        paths = self.table.selected_or_all()
        video_paths = [p for p in paths if p.suffix.lower() in _VIDEO_EXTS]
        if not video_paths:
            QMessageBox.information(self, "提示", "请先添加视频文件")
            return
        track = next((t for t in self._timeline.tracks if t.type == "video"), None)
        if track is None:
            track = self.timeline.add_track("video")
        added: Clip | None = None
        for p in video_paths:
            duration = probe_video_duration(p) or _DEFAULT_CLIP_SEC
            clip = Clip(
                id="",
                source_file=str(p),
                timeline_in=self._timeline.duration,
                source_in=0.0,
                source_out=duration,
            )
            track.add_clip(clip)
            self.preview.set_source(str(p))
            added = clip
        self.timeline.refresh()
        if added is not None:
            self.timeline.select_clip(added.id)

    def _on_clip_selected(self, clip_id: str) -> None:
        clip = self._timeline.find_clip(clip_id)
        self.params_panel.show_for_clip(clip)

    def _split_clip(self, clip_id: str, time: float) -> None:
        self._engine.execute(SplitClipCommand(clip_id, time))
        self.timeline.refresh()
        self.params_panel.refresh()
        self._sync_edit_buttons()

    def _adjust_params(self, clip_id: str, partial: dict) -> None:
        self._engine.execute(AdjustParamsCommand(clip_id, partial))
        self.timeline.refresh()
        self.params_panel.refresh()
        self._sync_edit_buttons()

    def _undo(self) -> None:
        if self._engine.undo():
            self.timeline.refresh()
            self.params_panel.refresh()
        self._sync_edit_buttons()

    def _redo(self) -> None:
        if self._engine.redo():
            self.timeline.refresh()
            self.params_panel.refresh()
        self._sync_edit_buttons()

    def _sync_edit_buttons(self) -> None:
        self.undo_btn.setEnabled(bool(self._engine.undo_stack))
        self.redo_btn.setEnabled(bool(self._engine.redo_stack))

    def _default_export_path(self) -> str:
        for track in self._timeline.tracks:
            for clip in track.clips:
                src = Path(clip.source_file)
                if src.suffix.lower() in _VIDEO_EXTS:
                    return str(src.with_name(f"{src.stem}_edited.mp4"))
        last_dir = self._settings.get("last_dir") or ""
        if last_dir:
            return str(Path(last_dir) / "output.mp4")
        return "output.mp4"

    def _has_video_clips(self) -> bool:
        return any(t.type == "video" and t.clips for t in self._timeline.tracks)

    def _open_export_dialog(self) -> None:
        if not self._has_video_clips():
            QMessageBox.information(self, "提示", "时间线上没有片段")
            return
        if not self._check_ffmpeg():
            QMessageBox.warning(self, "提示", "未找到 ffmpeg，无法导出视频")
            return
        dialog = _ExportDialog(self._default_export_path(), self)
        self._export_dialog = dialog
        dialog.start_requested.connect(self._run_export)
        dialog.cancel_requested.connect(self._cancel_export)
        dialog.set_progress(0, "")
        dialog.show()

    def _run_export(self, settings: dict) -> None:
        dialog = self._export_dialog
        if dialog is None:
            return
        dialog.disable_start()
        dialog.set_progress(0, "正在导出…")
        self._export_thread = _ExportThread(self._exporter, self._timeline, settings)
        self._export_thread.progress.connect(dialog.set_progress)
        self._export_thread.finished.connect(
            lambda data: self._export_done(data, dialog.output_path)
        )
        self._export_thread.failed.connect(self._export_failed)
        self._export_thread.start()

    def _cancel_export(self) -> None:
        thread = self._export_thread
        if thread is not None and thread.isRunning():
            thread.cancel()
            thread.wait(3000)

    def _export_done(self, data: bytes, out_path: str) -> None:
        try:
            Path(out_path).write_bytes(data)
        except OSError as e:
            QMessageBox.warning(self, "保存失败", friendly_error(e))
            return
        if self._export_dialog is not None:
            self._export_dialog.accept()
        QMessageBox.information(self, "导出完成", f"视频已保存到：\n{out_path}")

    def _export_failed(self, msg: str) -> None:
        if self._export_dialog is not None:
            self._export_dialog.accept()
        QMessageBox.warning(self, "导出失败", msg)
