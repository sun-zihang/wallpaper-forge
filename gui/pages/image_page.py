from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.tasks import OutputMode, Task, TaskKind, resolve_outputs
from gui.dialogs import CropDialog, WatermarkDialog
from gui.pages.base import BasePage

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
_OUT_EXTS = {
    "PNG": ".png",
    "JPG": ".jpg",
    "WebP": ".webp",
    "BMP": ".bmp",
    "GIF": ".gif",
}


class ImagePage(BasePage):
    def __init__(self):
        super().__init__(_IMAGE_EXTS)

        options = QGroupBox("转换选项")
        row = QHBoxLayout(options)

        row.addWidget(QLabel("输出格式："))
        self.fmt = QComboBox()
        self.fmt.addItems(["PNG", "JPG", "WebP", "BMP", "GIF"])
        self.fmt.setCurrentText("JPG")
        row.addWidget(self.fmt)

        self.scale_enable = QCheckBox("等比缩放到宽度")
        row.addWidget(self.scale_enable)
        self.scale_w = QSpinBox()
        self.scale_w.setRange(16, 8192)
        self.scale_w.setValue(1920)
        self.scale_w.setSuffix(" px")
        self.scale_w.setEnabled(False)
        row.addWidget(self.scale_w)
        self.scale_enable.toggled.connect(self.scale_w.setEnabled)

        row.addWidget(QLabel("质量："))
        self.quality = QSlider(Qt.Horizontal)
        self.quality.setRange(1, 100)
        self.quality.setValue(90)
        self.quality.setFixedWidth(140)
        self.quality_label = QLabel("90")
        self.quality.valueChanged.connect(lambda v: self.quality_label.setText(str(v)))
        row.addWidget(self.quality)
        row.addWidget(self.quality_label)

        row.addStretch(1)
        self.crop_btn = QPushButton("裁剪…")
        self.crop_btn.setObjectName("secondary")
        self.wm_btn = QPushButton("水印…")
        self.wm_btn.setObjectName("secondary")
        row.addWidget(self.crop_btn)
        row.addWidget(self.wm_btn)

        self.crop_btn.clicked.connect(self._crop)
        self.wm_btn.clicked.connect(self._watermark)
        self.fmt.currentTextChanged.connect(self._on_fmt_changed)

        mid = QWidget()
        layout = QVBoxLayout(mid)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(options)
        layout.addWidget(self.table, 1)
        self.finish_layout(mid)

    def apply_settings(self, settings: dict) -> None:
        super().apply_settings(settings)
        fmt = settings.get("last_image_format") or "JPG"
        if fmt in _OUT_EXTS:
            self.fmt.blockSignals(True)
            self.fmt.setCurrentText(fmt)
            self.fmt.blockSignals(False)
        try:
            q = int(settings.get("default_quality", 90))
        except (TypeError, ValueError):
            q = 90
        q = max(1, min(100, q))
        self.quality.blockSignals(True)
        self.quality.setValue(q)
        self.quality.blockSignals(False)
        self.quality_label.setText(str(q))

    def _on_fmt_changed(self, text: str) -> None:
        self._persist({"last_image_format": text})

    def start_batch(self) -> None:
        paths = self._batch_paths()
        paths = [p for p in paths if p.suffix.lower() in _IMAGE_EXTS]
        if not paths:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(self, "提示", "请先添加图片文件")
            return
        ext = _OUT_EXTS[self.fmt.currentText()]
        mode = self.output_mode_value()
        if mode is OutputMode.UNIFIED and self.unified_dir is None:
            return
        outs = resolve_outputs(paths, ext, mode, self.unified_dir, overwrite=self.overwrite_check.isChecked())
        if not self._confirm_overwrite(paths, outs):
            return
        task = Task(
            sources=paths,
            kind=TaskKind.IMAGE_CONVERT,
            params={
                "quality": int(self.quality.value()),
                "max_width": int(self.scale_w.value()) if self.scale_enable.isChecked() else 0,
            },
            output_mode=mode,
            unified_dir=self.unified_dir,
            outputs=outs,
        )
        self._submit([task])

    def _crop(self) -> None:
        paths = self.table.selected_or_all()
        if not paths:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(self, "提示", "请先选中一张图片")
            return
        src = paths[0]
        if len(paths) > 1:
            self._on_status(f"裁剪使用第一个选中文件：{src.name}")
        box = CropDialog.get_box(self, src)
        if box is None:
            return
        mode = self.output_mode_value()
        if mode is OutputMode.UNIFIED and self.unified_dir is None:
            return
        outs = resolve_outputs([src], src.suffix.lstrip("."), mode, self.unified_dir, op_subdir="converted", overwrite=self.overwrite_check.isChecked())
        if not self._confirm_overwrite([src], outs):
            return
        # avoid identical in-place: resolve_outputs handles collision
        task = Task(
            sources=[src],
            kind=TaskKind.IMAGE_EDIT,
            params={"op": "crop", "box": box},
            output_mode=mode,
            unified_dir=self.unified_dir,
            outputs=outs,
        )
        self._submit([task])

    def _watermark(self) -> None:
        paths = self.table.selected_or_all()
        paths = [p for p in paths if p.suffix.lower() in _IMAGE_EXTS]
        if not paths:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(self, "提示", "请先添加并选中图片")
            return
        if len(paths) > 1:
            self._on_status(f"水印将处理 {len(paths)} 个文件")
        params = WatermarkDialog.get_params(self)
        if not params:
            return
        mode = self.output_mode_value()
        if mode is OutputMode.UNIFIED and self.unified_dir is None:
            return
        outs = resolve_outputs(
            [p for p in paths],
            paths[0].suffix.lstrip("."),
            mode,
            self.unified_dir,
            overwrite=self.overwrite_check.isChecked(),
        )
        if not self._confirm_overwrite(paths, outs):
            return
        task = Task(
            sources=paths,
            kind=TaskKind.IMAGE_EDIT,
            params=params,
            output_mode=mode,
            unified_dir=self.unified_dir,
            outputs=outs,
        )
        self._submit([task])
