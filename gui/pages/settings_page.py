from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.ffmpeg_finder import FFmpegNotFound, find_ffmpeg
from gui.settings_store import load_settings, save_settings
from gui.styles import FAIL, OK


class SettingsPage(QWidget):
    manual_update_check = Signal()

    def __init__(self, on_changed=None):
        super().__init__()
        self._on_changed = on_changed
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        out_box = QGroupBox("输出")
        g = QVBoxLayout(out_box)
        row = QHBoxLayout()
        row.addWidget(QLabel("默认输出模式："))
        self.mode = QComboBox()
        self.mode.addItem("源旁 converted 子目录", "beside")
        self.mode.addItem("统一目录", "unified")
        row.addWidget(self.mode)
        self.pick_btn = QPushButton("选择统一目录…")
        self.pick_btn.setObjectName("secondary")
        self.pick_btn.clicked.connect(self._pick)
        row.addWidget(self.pick_btn)
        row.addStretch(1)
        g.addLayout(row)
        self.dir_label = QLabel("")
        self.dir_label.setObjectName("pathText")
        g.addWidget(self.dir_label)

        quality_row = QHBoxLayout()
        quality_row.addWidget(QLabel("默认图片质量："))
        self.quality = QSpinBox()
        self.quality.setRange(1, 100)
        self.quality.setValue(90)
        quality_row.addWidget(self.quality)
        quality_row.addSpacing(20)
        quality_row.addWidget(QLabel("默认 GIF 帧率："))
        self.gif_fps = QSpinBox()
        self.gif_fps.setRange(1, 50)
        self.gif_fps.setValue(15)
        quality_row.addWidget(self.gif_fps)
        quality_row.addStretch(1)
        g.addLayout(quality_row)

        ff_box = QGroupBox("FFmpeg")
        frow = QHBoxLayout(ff_box)
        self.ff_label = QLabel("检测中…")
        self.ff_label.setWordWrap(True)
        self.ff_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        frow.addWidget(self.ff_label, 1)
        self.recheck = QPushButton("重新检测")
        self.recheck.setObjectName("secondary")
        self.recheck.clicked.connect(self._recheck)
        frow.addWidget(self.recheck)

        upd_box = QGroupBox("更新")
        urow = QHBoxLayout(upd_box)
        self.auto_check = QCheckBox("启动时自动检查更新")
        urow.addWidget(self.auto_check)
        self.check_btn = QPushButton("检查更新")
        self.check_btn.setObjectName("secondary")
        self.check_btn.clicked.connect(self.manual_update_check.emit)
        urow.addWidget(self.check_btn)
        urow.addStretch(1)

        about = QLabel(
            "Wallpaper Converter\n"
            "图片/视频壁纸批量格式转换工具\n"
            "依赖：Pillow (BSD)、PySide6 (LGPL)、FFmpeg (LGPL)"
        )
        about.setObjectName("mutedText")

        save_btn = QPushButton("保存设置")
        save_btn.clicked.connect(self._save)

        root.addWidget(out_box)
        root.addWidget(ff_box)
        root.addWidget(upd_box)
        root.addWidget(about)
        root.addStretch(1)
        root.addWidget(save_btn, alignment=Qt.AlignRight)

        self._unified_dir: Path | None = None
        self._load()

    def _load(self) -> None:
        s = load_settings()
        self.mode.setCurrentIndex(1 if s.get("output_mode") == "unified" else 0)
        if s.get("unified_dir"):
            self._unified_dir = Path(s["unified_dir"])
            self.dir_label.setText(str(self._unified_dir))
        self.quality.setValue(int(s.get("default_quality", 90)))
        self.gif_fps.setValue(int(s.get("default_gif_fps", 15)))
        self.auto_check.setChecked(bool(s.get("auto_check_update", True)))
        self.refresh_ffmpeg()

    def _pick(self) -> None:
        dir_ = QFileDialog.getExistingDirectory(self, "选择统一输出目录")
        if dir_:
            self._unified_dir = Path(dir_)
            self.dir_label.setText(dir_)

    def _save(self) -> None:
        save_settings(
            {
                "output_mode": self.mode.currentData(),
                "unified_dir": str(self._unified_dir or ""),
                "default_quality": self.quality.value(),
                "default_gif_fps": self.gif_fps.value(),
                "auto_check_update": self.auto_check.isChecked(),
            }
        )
        if self._on_changed:
            self._on_changed()

    def refresh_ffmpeg(self) -> None:
        try:
            p = find_ffmpeg()
            self.ff_label.setText(f"已找到：{p}")
            self.ff_label.setStyleSheet(f"color: {OK};")
        except FFmpegNotFound:
            self.ff_label.setText("未找到 ffmpeg（视频功能不可用）")
            self.ff_label.setStyleSheet(f"color: {FAIL};")

    def _recheck(self) -> None:
        self.refresh_ffmpeg()
        if self._on_changed:
            self._on_changed()
