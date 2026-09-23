from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.ffmpeg_finder import ffmpeg_available
from core.tasks import OutputMode, Task, TaskKind, resolve_outputs
from gui.pages.base import BasePage

_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv"}
_OUT = {
    "MP4": ".mp4",
    "WebM": ".webm",
    "MOV": ".mov",
    "MKV": ".mkv",
}


class VideoPage(BasePage):
    def __init__(self):
        super().__init__(_VIDEO_EXTS)
        self._ffmpeg_ok = True

        self.banner = QLabel("未检测到 ffmpeg，视频功能不可用。请安装 ffmpeg 或设置 WALLPAPER_FORGE_FFMPEG。")
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
        self.lbl_every = QLabel("每 N 秒一帧：")
        self.every = QDoubleSpinBox()
        self.every.setRange(0.1, 3600)
        self.every.setValue(1.0)
        self.frame_ext = QComboBox()
        self.frame_ext.addItems(["png", "jpg", "webp"])
        self.lbl_ext = QLabel("图片格式：")
        self.frame_widgets = [(self.lbl_every, self.every), (self.lbl_ext, self.frame_ext)]

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
        self._sync_mode()

        mid = QWidget()
        layout = QVBoxLayout(mid)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.banner)
        layout.addWidget(options)
        layout.addWidget(self.table, 1)
        self.finish_layout(mid)

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
            vis = kind == "frames"
            lbl.setVisible(vis)
            w.setVisible(vis)
        for lbl, w in self.trim_widgets:
            vis = kind == "trim"
            lbl.setVisible(vis)
            w.setVisible(vis)

    def set_ffmpeg_ok(self, ok: bool) -> None:
        self._ffmpeg_ok = ok
        self.banner.setVisible(not ok)
        self.start_btn.setEnabled(ok and not self.thread.isRunning())

    def start_batch(self) -> None:
        if not ffmpeg_available():
            QMessageBox.warning(self, "提示", "未找到 ffmpeg，无法处理视频")
            return
        paths = self.table.selected_or_all()
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
            outs = resolve_outputs(paths, ext, out_mode, self.unified_dir)
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
            outs = resolve_outputs(paths, ".gif", out_mode, self.unified_dir)
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
            # one task per source so each writes its own folder
            batch = []
            for p in paths:
                if out_mode is OutputMode.UNIFIED:
                    out_dir = self.unified_dir / f"{p.stem}_frames"
                else:
                    out_dir = p.parent / "converted" / f"{p.stem}_frames"
                batch.append(
                    Task(
                        sources=[p],
                        kind=TaskKind.VIDEO_EXTRACT_FRAMES,
                        params={
                            "every_seconds": self.every.value(),
                            "ext": self.frame_ext.currentText(),
                            "out_dir": out_dir,
                        },
                        output_mode=out_mode,
                        unified_dir=self.unified_dir,
                        outputs=[],
                    )
                )
            self._submit(batch)
        elif mode == "trim":
            # single file trim typically
            if len(paths) > 1:
                QMessageBox.information(self, "提示", "片段截取一次请选择一个视频")
                return
            outs = resolve_outputs(paths, ".mp4", out_mode, self.unified_dir)
            task = Task(
                sources=paths,
                kind=TaskKind.VIDEO_TRIM,
                params={"start": self.t_start.value(), "end": self.t_end.value()},
                output_mode=out_mode,
                unified_dir=self.unified_dir,
                outputs=outs,
            )
            self._submit([task])
