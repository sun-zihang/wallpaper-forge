from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.ffmpeg_finder import ffmpeg_available
from core.tasks import OutputMode, Task, TaskKind, resolve_out_dir, resolve_outputs
from gui.pages.base import BasePage

_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv"}
_OUT = {
    "MP4": ".mp4",
    "WebM": ".webm",
    "MOV": ".mov",
    "MKV": ".mkv",
}
_MAX_AT_SECONDS = 200


def parse_at_seconds(text: str) -> list[float]:
    parts = [part.strip() for part in text.replace("，", ",").split(",")]
    if not parts or any(not part for part in parts):
        raise ValueError("请输入有效的指定时间点")
    values = []
    for part in parts:
        try:
            value = float(part)
        except ValueError as exc:
            raise ValueError(f"时间点“{part}”不是有效数字") from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError("指定时间点必须是正数")
        values.append(value)
    values = sorted(set(values))
    if len(values) > _MAX_AT_SECONDS:
        raise ValueError(f"指定时间点最多 {_MAX_AT_SECONDS} 个")
    return values


class VideoPage(BasePage):
    def __init__(self):
        super().__init__(_VIDEO_EXTS)
        self._ffmpeg_ok = True

        self.banner = QLabel(
            "未检测到 ffmpeg，视频功能不可用。请安装 ffmpeg 或设置 WALLPAPER_FORGE_FFMPEG。"
        )
        self.banner.setObjectName("banner")
        self.banner.hide()

        options = QGroupBox("转换选项")
        row = QHBoxLayout(options)

        row.addWidget(QLabel("模式："))
        self.mode = QComboBox()
        self.mode.addItem("格式互转", "convert")
        self.mode.addItem("视频转 GIF", "gif")
        self.mode.addItem("截取帧", "frames")
        self.mode.addItem("片段截取", "trim")
        row.addWidget(self.mode)

        # convert opts
        self.fmt = QComboBox()
        self.fmt.addItems(["MP4", "WebM", "MOV", "MKV"])
        self.keep_audio = QCheckBox("保留音频")
        self.keep_audio.setChecked(True)
        self.lbl_fmt = QLabel("输出：")
        row.addWidget(self.lbl_fmt)
        row.addWidget(self.fmt)
        row.addWidget(self.keep_audio)

        # gif opts
        self.lbl_gif_fps = QLabel("GIF 帧率：")
        self.gif_fps = QSpinBox()
        self.gif_fps.setRange(1, 50)
        self.gif_fps.setValue(15)
        self.lbl_gif_w = QLabel("宽度：")
        self.gif_w = QSpinBox()
        self.gif_w.setRange(16, 3840)
        self.gif_w.setValue(480)
        self.gif_w.setSingleStep(16)
        self.lbl_gif_dur = QLabel("时长上限(秒，0=不限)：")
        self.gif_dur = QDoubleSpinBox()
        self.gif_dur.setRange(0, 3600)
        self.gif_dur.setDecimals(1)
        self.gif_widgets = [
            (self.lbl_gif_fps, self.gif_fps),
            (self.lbl_gif_w, self.gif_w),
            (self.lbl_gif_dur, self.gif_dur),
        ]

        # frames opts
        self.lbl_frame_mode = QLabel("截帧方式：")
        self.frame_mode = QComboBox()
        self.frame_mode.addItem("每 N 秒", "interval")
        self.frame_mode.addItem("指定时间点", "at")
        self.lbl_every = QLabel("每 N 秒一帧：")
        self.every = QDoubleSpinBox()
        self.every.setRange(0.1, 3600)
        self.every.setValue(1.0)
        self.lbl_at_seconds = QLabel("时间点(秒)：")
        self.at_seconds_edit = QLineEdit("0.5, 2, 10")
        self.at_seconds_edit.setPlaceholderText("例如：0.5, 2, 10")
        self.at_seconds_edit.setMinimumWidth(180)
        self.frame_ext = QComboBox()
        self.frame_ext.addItems(["png", "jpg", "webp"])
        self.lbl_ext = QLabel("图片格式：")
        self.frame_widgets = [
            (self.lbl_frame_mode, self.frame_mode),
            (self.lbl_every, self.every),
            (self.lbl_at_seconds, self.at_seconds_edit),
            (self.lbl_ext, self.frame_ext),
        ]

        # trim opts
        self.lbl_start = QLabel("开始(秒)：")
        self.t_start = QDoubleSpinBox()
        self.t_start.setRange(0, 86400)
        self.lbl_end = QLabel("结束(秒)：")
        self.t_end = QDoubleSpinBox()
        self.t_end.setRange(0.1, 86400)
        self.t_end.setValue(5)
        self.trim_widgets = [(self.lbl_start, self.t_start), (self.lbl_end, self.t_end)]

        for pair_list in (self.gif_widgets, self.frame_widgets, self.trim_widgets):
            for lbl, w in pair_list:
                row.addWidget(lbl)
                row.addWidget(w)
        row.addStretch(1)

        self.mode.currentIndexChanged.connect(self._sync_mode)
        self.frame_mode.currentIndexChanged.connect(self._sync_frame_mode)
        self.fmt.currentTextChanged.connect(self._on_fmt_changed)
        self._sync_mode()

        mid = QWidget()
        layout = QVBoxLayout(mid)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.banner)
        layout.addWidget(options)
        layout.addWidget(self.table, 1)
        self.finish_layout(mid)

    def apply_settings(self, settings: dict) -> None:
        super().apply_settings(settings)
        fmt = settings.get("last_video_format") or "MP4"
        if fmt in _OUT:
            self.fmt.blockSignals(True)
            self.fmt.setCurrentText(fmt)
            self.fmt.blockSignals(False)
        try:
            fps = int(settings.get("default_gif_fps", 15))
        except (TypeError, ValueError):
            fps = 15
        self.gif_fps.setValue(max(1, min(50, fps)))

    def _on_fmt_changed(self, text: str) -> None:
        self._persist({"last_video_format": text})

    def _sync_mode(self) -> None:
        kind = self.mode.currentData()
        show_convert = kind == "convert"
        self.lbl_fmt.setVisible(show_convert)
        self.fmt.setVisible(show_convert)
        self.keep_audio.setVisible(show_convert)
        for lbl, w in self.gif_widgets:
            vis = kind == "gif"
            lbl.setVisible(vis)
            w.setVisible(vis)
        for lbl, w in self.frame_widgets:
            lbl.setVisible(kind == "frames")
            w.setVisible(kind == "frames")
        for lbl, w in self.trim_widgets:
            vis = kind == "trim"
            lbl.setVisible(vis)
            w.setVisible(vis)
        self._sync_frame_mode()

    def _sync_frame_mode(self) -> None:
        show_frames = self.mode.currentData() == "frames"
        at_mode = show_frames and self.frame_mode.currentData() == "at"
        self.lbl_every.setVisible(show_frames and not at_mode)
        self.every.setVisible(show_frames and not at_mode)
        self.lbl_at_seconds.setVisible(at_mode)
        self.at_seconds_edit.setVisible(at_mode)

    def set_ffmpeg_ok(self, ok: bool) -> None:
        self._ffmpeg_ok = ok
        self.banner.setVisible(not ok)
        self.start_btn.setEnabled(ok and not self.thread.isRunning())

    def start_batch(self) -> None:
        if not ffmpeg_available():
            QMessageBox.warning(self, "提示", "未找到 ffmpeg，无法处理视频")
            return
        paths = self._batch_paths()
        paths = [p for p in paths if p.suffix.lower() in _VIDEO_EXTS]
        if not paths:
            QMessageBox.information(self, "提示", "请先添加视频文件")
            return
        mode = self.mode.currentData()
        out_mode = self.output_mode_value()
        if out_mode is OutputMode.UNIFIED and self.unified_dir is None:
            return

        if mode == "convert":
            ext = _OUT[self.fmt.currentText()]
            ow = self.overwrite_check.isChecked()
            outs = resolve_outputs(paths, ext, out_mode, self.unified_dir, overwrite=ow)
            if not self._confirm_overwrite(paths, outs):
                return
            task = Task(
                sources=paths,
                kind=TaskKind.VIDEO_CONVERT,
                params={"keep_audio": self.keep_audio.isChecked()},
                output_mode=out_mode,
                unified_dir=self.unified_dir,
                outputs=outs,
            )
            self._submit([task])
        elif mode == "gif":
            ow = self.overwrite_check.isChecked()
            outs = resolve_outputs(paths, ".gif", out_mode, self.unified_dir, overwrite=ow)
            if not self._confirm_overwrite(paths, outs):
                return
            dur = self.gif_dur.value() or None
            task = Task(
                sources=paths,
                kind=TaskKind.VIDEO_TO_GIF,
                params={
                    "fps": self.gif_fps.value(),
                    "width": self.gif_w.value(),
                    "max_duration": dur,
                },
                output_mode=out_mode,
                unified_dir=self.unified_dir,
                outputs=outs,
            )
            self._submit([task])
        elif mode == "frames":
            at_seconds = None
            if self.frame_mode.currentData() == "at":
                try:
                    at_seconds = parse_at_seconds(self.at_seconds_edit.text())
                except ValueError as exc:
                    QMessageBox.warning(self, "截帧时间无效", str(exc))
                    return
            ow = self.overwrite_check.isChecked()
            batch = []
            out_dirs: list[Path] = []
            taken: set[Path] = set()
            for p in paths:
                out_dir = resolve_out_dir(
                    p,
                    out_mode,
                    self.unified_dir,
                    name_suffix="_frames",
                    overwrite=ow,
                    taken=taken,
                )
                out_dirs.append(out_dir)
                params = {
                    "ext": self.frame_ext.currentText(),
                    "out_dir": out_dir,
                }
                if at_seconds is not None:
                    params["at_seconds"] = at_seconds
                else:
                    params["every_seconds"] = self.every.value()
                batch.append(
                    Task(
                        sources=[p],
                        kind=TaskKind.VIDEO_EXTRACT_FRAMES,
                        params=params,
                        output_mode=out_mode,
                        unified_dir=self.unified_dir,
                        outputs=[],
                    )
                )
            # out_dirs are directories, so resolve-equality with file sources is structurally impossible (can never fire; correct per design).
            if not self._confirm_overwrite(paths, out_dirs):
                return
            self._submit(batch)
        elif mode == "trim":
            # single file trim typically
            if len(paths) > 1:
                QMessageBox.information(self, "提示", "片段截取一次请选择一个视频")
                return
            ow = self.overwrite_check.isChecked()
            outs = resolve_outputs(paths, ".mp4", out_mode, self.unified_dir, overwrite=ow)
            if not self._confirm_overwrite(paths, outs):
                return
            task = Task(
                sources=paths,
                kind=TaskKind.VIDEO_TRIM,
                params={"start": self.t_start.value(), "end": self.t_end.value()},
                output_mode=out_mode,
                unified_dir=self.unified_dir,
                outputs=outs,
            )
            self._submit([task])
