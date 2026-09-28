from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui.video_edit.model import Clip

_ROTATIONS = [0, 90, 180, 270]


def _slider_widgets(text: str, min_val: int, max_val: int, value: int, fmt: str):
    label = QLabel(text)
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(min_val, max_val)
    slider.setValue(value)
    value_label = QLabel(fmt.format(value))
    value_label.setFixedWidth(52)
    value_label.setObjectName("pathText")
    return label, slider, value_label


def _overlay_default() -> dict:
    return {
        "type": "text",
        "text": "文字",
        "fontSize": 24,
        "fontColor": "#ffffff",
        "opacity": 1.0,
        "position": {"x": 50, "y": 50},
    }


class ParamsPanel(QWidget):
    params_changed = Signal(str, dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._clip: Clip | None = None
        self._updating = False
        self._overlay_color = QColor("#ffffff")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.empty_label = QLabel("请先在时间线中选中一个片段")
        self.empty_label.setObjectName("banner")
        self.empty_label.setWordWrap(True)
        root.addWidget(self.empty_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        container = QWidget()
        form = QVBoxLayout(container)
        form.setContentsMargins(8, 4, 8, 4)
        form.setSpacing(8)

        form.addWidget(self._build_playback(container))
        form.addWidget(self._build_transform(container))
        form.addWidget(self._build_grade(container))
        form.addWidget(self._build_overlay(container))
        form.addStretch(1)

        self.scroll_area.setWidget(container)
        root.addWidget(self.scroll_area, 1)

    def _build_playback(self, parent) -> QGroupBox:
        box = QGroupBox("播放")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        row.addWidget(QLabel("速度："))
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.1, 8.0)
        self.speed_spin.setSingleStep(0.1)
        self.speed_spin.setValue(1.0)
        self.speed_spin.setSuffix("x")
        row.addWidget(self.speed_spin, 1)
        layout.addLayout(row)
        self.speed_spin.valueChanged.connect(lambda v: self._emit({"speed": round(v, 2)}))

        label, slider, value_label = _slider_widgets("音量：", 0, 200, 100, "{:.0f}%")
        self.volume_slider = slider
        self.volume_label = value_label
        row = QHBoxLayout()
        row.addWidget(label)
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        layout.addLayout(row)
        slider.valueChanged.connect(
            lambda v: self._slider_emit(value_label, v, "{:.0f}%", {"audio": {"volume": v / 100}})
        )

        row = QHBoxLayout()
        row.addWidget(QLabel("淡入(秒)："))
        self.fade_in_spin = QDoubleSpinBox()
        self.fade_in_spin.setRange(0, 60)
        self.fade_in_spin.setSingleStep(0.1)
        row.addWidget(self.fade_in_spin, 1)
        layout.addLayout(row)
        self.fade_in_spin.valueChanged.connect(
            lambda v: self._emit({"audio": {"fade_in": round(v, 2)}})
        )

        row = QHBoxLayout()
        row.addWidget(QLabel("淡出(秒)："))
        self.fade_out_spin = QDoubleSpinBox()
        self.fade_out_spin.setRange(0, 60)
        self.fade_out_spin.setSingleStep(0.1)
        row.addWidget(self.fade_out_spin, 1)
        layout.addLayout(row)
        self.fade_out_spin.valueChanged.connect(
            lambda v: self._emit({"audio": {"fade_out": round(v, 2)}})
        )
        return box

    def _build_transform(self, parent) -> QGroupBox:
        box = QGroupBox("画面")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        row.addWidget(QLabel("旋转："))
        self.rotation_combo = QComboBox()
        for deg in _ROTATIONS:
            self.rotation_combo.addItem(f"{deg}°", deg)
        row.addWidget(self.rotation_combo, 1)
        layout.addLayout(row)
        self.rotation_combo.currentIndexChanged.connect(
            lambda i: self._emit({"transform": {"rotation": _ROTATIONS[i]}})
        )

        self.flip_h_check = QCheckBox("水平翻转")
        layout.addWidget(self.flip_h_check)
        self.flip_h_check.toggled.connect(lambda on: self._emit({"transform": {"flip_h": on}}))

        self.flip_v_check = QCheckBox("垂直翻转")
        layout.addWidget(self.flip_v_check)
        self.flip_v_check.toggled.connect(lambda on: self._emit({"transform": {"flip_v": on}}))

        label, slider, value_label = _slider_widgets("缩放：", 10, 300, 100, "{:.0f}%")
        self.scale_slider = slider
        self.scale_label = value_label
        row = QHBoxLayout()
        row.addWidget(label)
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        layout.addLayout(row)
        slider.valueChanged.connect(
            lambda v: self._slider_emit(
                value_label, v, "{:.0f}%", {"transform": {"scale": v / 100}}
            )
        )

        self.crop_check = QCheckBox("启用裁剪")
        layout.addWidget(self.crop_check)
        self.crop_check.toggled.connect(lambda on: self._emit_crop())
        crop_row = QHBoxLayout()
        self.crop_x = QDoubleSpinBox()
        self.crop_y = QDoubleSpinBox()
        self.crop_w = QDoubleSpinBox()
        self.crop_h = QDoubleSpinBox()
        for spin, name in (
            (self.crop_x, "X"),
            (self.crop_y, "Y"),
            (self.crop_w, "宽"),
            (self.crop_h, "高"),
        ):
            spin.setRange(0, 100000)
            spin.setDecimals(1)
            crop_row.addWidget(QLabel(name))
            crop_row.addWidget(spin)
        layout.addLayout(crop_row)
        for spin in (self.crop_x, self.crop_y, self.crop_w, self.crop_h):
            spin.valueChanged.connect(lambda *_: self._emit_crop())
        return box

    def _build_grade(self, parent) -> QGroupBox:
        box = QGroupBox("调色")
        layout = QVBoxLayout(box)

        self._grade_sliders: dict[str, tuple[QSlider, QLabel]] = {}
        for text, key in (
            ("亮度：", "brightness"),
            ("对比度：", "contrast"),
            ("饱和度：", "saturation"),
        ):
            label, slider, value_label = _slider_widgets(text, -100, 100, 0, "{:+.0f}")
            row = QHBoxLayout()
            row.addWidget(label)
            row.addWidget(slider, 1)
            row.addWidget(value_label)
            layout.addLayout(row)
            self._grade_sliders[key] = (slider, value_label)
            slider.valueChanged.connect(
                lambda v, k=key, lbl=value_label: self._slider_emit(
                    lbl, v, "{:+.0f}", {"filters": {k: v / 100}}
                )
            )

        label, slider, value_label = _slider_widgets("色相：", 0, 360, 0, "{:+.0f}°")
        row = QHBoxLayout()
        row.addWidget(label)
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        layout.addLayout(row)
        self._grade_sliders["hue"] = (slider, value_label)
        slider.valueChanged.connect(
            lambda v: self._slider_emit(value_label, v, "{:+.0f}°", {"filters": {"hue": v}})
        )

        self.grayscale_check = QCheckBox("灰度")
        layout.addWidget(self.grayscale_check)
        self.grayscale_check.toggled.connect(lambda on: self._emit({"filters": {"grayscale": on}}))

        self.sepia_check = QCheckBox("怀旧")
        layout.addWidget(self.sepia_check)
        self.sepia_check.toggled.connect(lambda on: self._emit({"filters": {"sepia": on}}))

        label, slider, value_label = _slider_widgets("模糊：", 0, 200, 0, "{:.1f}")
        row = QHBoxLayout()
        row.addWidget(label)
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        layout.addLayout(row)
        self._grade_sliders["blur"] = (slider, value_label)
        slider.valueChanged.connect(
            lambda v: self._slider_emit(value_label, v, "{:.1f}", {"filters": {"blur": v / 10}})
        )

        label, slider, value_label = _slider_widgets("锐化：", 0, 100, 0, "{:.1f}")
        row = QHBoxLayout()
        row.addWidget(label)
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        layout.addLayout(row)
        self._grade_sliders["sharpen"] = (slider, value_label)
        slider.valueChanged.connect(
            lambda v: self._slider_emit(value_label, v, "{:.1f}", {"filters": {"sharpen": v / 10}})
        )
        return box

    def _build_overlay(self, parent) -> QGroupBox:
        box = QGroupBox("叠加")
        layout = QVBoxLayout(box)

        self.overlay_check = QCheckBox("启用文字叠加")
        layout.addWidget(self.overlay_check)
        self.overlay_check.toggled.connect(self._emit_overlay_enabled)

        row = QHBoxLayout()
        row.addWidget(QLabel("内容："))
        self.overlay_text = QLineEdit("文字")
        row.addWidget(self.overlay_text, 1)
        layout.addLayout(row)
        self.overlay_text.textChanged.connect(lambda *_: self._emit_overlay())

        row = QHBoxLayout()
        row.addWidget(QLabel("字号："))
        self.overlay_font_size = QSpinBox()
        self.overlay_font_size.setRange(8, 200)
        self.overlay_font_size.setValue(24)
        row.addWidget(self.overlay_font_size, 1)
        layout.addLayout(row)
        self.overlay_font_size.valueChanged.connect(lambda *_: self._emit_overlay())

        row = QHBoxLayout()
        row.addWidget(QLabel("颜色："))
        self.overlay_color_btn = QPushButton("选择颜色")
        self.overlay_color_btn.setObjectName("secondary")
        row.addWidget(self.overlay_color_btn, 1)
        layout.addLayout(row)
        self.overlay_color_btn.clicked.connect(self._pick_overlay_color)

        label, slider, value_label = _slider_widgets("位置 X：", 0, 100, 50, "{:.0f}%")
        self.overlay_x_slider = slider
        self.overlay_x_label = value_label
        row = QHBoxLayout()
        row.addWidget(label)
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        layout.addLayout(row)
        slider.valueChanged.connect(
            lambda v: self._slider_emit(
                value_label, v, "{:.0f}%", {"overlay": self._overlay_from_widgets()}
            )
        )

        label, slider, value_label = _slider_widgets("位置 Y：", 0, 100, 50, "{:.0f}%")
        self.overlay_y_slider = slider
        self.overlay_y_label = value_label
        row = QHBoxLayout()
        row.addWidget(label)
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        layout.addLayout(row)
        slider.valueChanged.connect(
            lambda v: self._slider_emit(
                value_label, v, "{:.0f}%", {"overlay": self._overlay_from_widgets()}
            )
        )

        label, slider, value_label = _slider_widgets("透明度：", 0, 100, 100, "{:.0f}%")
        self.opacity_slider = slider
        self.opacity_label = value_label
        row = QHBoxLayout()
        row.addWidget(label)
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        layout.addLayout(row)
        slider.valueChanged.connect(
            lambda v: self._slider_emit(
                value_label, v, "{:.0f}%", {"overlay": self._overlay_from_widgets(v / 100)}
            )
        )
        return box

    def _slider_emit(self, label: QLabel, value: int, fmt: str, partial: dict) -> None:
        label.setText(fmt.format(value))
        self._emit(partial)

    def _emit(self, partial: dict) -> None:
        if self._clip is None or self._updating:
            return
        self.params_changed.emit(self._clip.id, partial)

    def _emit_crop(self) -> None:
        if not self.crop_check.isChecked():
            self._emit({"transform": {"crop": None}})
            return
        self._emit(
            {
                "transform": {
                    "crop": {
                        "x": self.crop_x.value(),
                        "y": self.crop_y.value(),
                        "width": self.crop_w.value(),
                        "height": self.crop_h.value(),
                    }
                }
            }
        )

    def _overlay_from_widgets(self, opacity: float | None = None) -> dict:
        overlay = _overlay_default()
        overlay["text"] = self.overlay_text.text()
        overlay["fontSize"] = self.overlay_font_size.value()
        overlay["fontColor"] = self._overlay_color.name()
        overlay["position"] = {
            "x": self.overlay_x_slider.value(),
            "y": self.overlay_y_slider.value(),
        }
        overlay["opacity"] = self.opacity_slider.value() / 100 if opacity is None else opacity
        return overlay

    def _emit_overlay(self) -> None:
        if not self.overlay_check.isChecked():
            return
        self._emit({"overlay": self._overlay_from_widgets()})

    def _emit_overlay_enabled(self, on: bool) -> None:
        if on:
            self._emit({"overlay": self._overlay_from_widgets()})
        else:
            self._emit({"overlay": None})

    def _pick_overlay_color(self) -> None:
        color = QColorDialog.getColor(self._overlay_color, self, "选择文字颜色")
        if color.isValid():
            self._overlay_color = color
            self._emit_overlay()

    def show_for_clip(self, clip: Clip | None) -> None:
        self._clip = clip
        if clip is None:
            self.empty_label.show()
            self.scroll_area.hide()
            return
        self.empty_label.hide()
        self.scroll_area.show()
        self.refresh()

    def refresh(self) -> None:
        clip = self._clip
        if clip is None:
            return
        p = clip.params
        self._updating = True
        try:
            self.speed_spin.setValue(clip.speed)
            audio = p["audio"]
            self.volume_slider.setValue(round(audio["volume"] * 100))
            self.volume_label.setText(f"{round(audio['volume'] * 100)}%")
            self.fade_in_spin.setValue(audio["fade_in"])
            self.fade_out_spin.setValue(audio["fade_out"])

            transform = p["transform"]
            rotation = transform.get("rotation", 0)
            self.rotation_combo.setCurrentIndex(
                _ROTATIONS.index(rotation) if rotation in _ROTATIONS else 0
            )
            self.flip_h_check.setChecked(transform.get("flip_h", False))
            self.flip_v_check.setChecked(transform.get("flip_v", False))
            scale_pct = round(transform.get("scale", 1.0) * 100)
            self.scale_slider.setValue(scale_pct)
            self.scale_label.setText(f"{scale_pct}%")
            crop = transform.get("crop")
            self.crop_check.setChecked(crop is not None)
            if crop is not None:
                self.crop_x.setValue(crop["x"])
                self.crop_y.setValue(crop["y"])
                self.crop_w.setValue(crop["width"])
                self.crop_h.setValue(crop["height"])

            filters = p["filters"]
            for key, (slider, label) in self._grade_sliders.items():
                value = filters.get(key, 0)
                if key in ("blur", "sharpen"):
                    slider.setValue(round(value * 10))
                    label.setText(f"{value:.1f}")
                elif key == "hue":
                    slider.setValue(value)
                    label.setText(f"{value:+d}°")
                else:
                    slider.setValue(round(value * 100))
                    label.setText(f"{round(value * 100):+d}")
            self.grayscale_check.setChecked(filters.get("grayscale", False))
            self.sepia_check.setChecked(filters.get("sepia", False))

            overlay = p.get("overlay")
            self.overlay_check.setChecked(overlay is not None)
            if overlay is not None:
                self.overlay_text.setText(overlay.get("text", ""))
                self.overlay_font_size.setValue(overlay.get("fontSize", 24))
                color = QColor(overlay.get("fontColor", "#ffffff"))
                if color.isValid():
                    self._overlay_color = color
                pos = overlay.get("position", {})
                x_pct = pos.get("x", 50)
                y_pct = pos.get("y", 50)
                self.overlay_x_slider.setValue(x_pct)
                self.overlay_x_label.setText(f"{x_pct}%")
                self.overlay_y_slider.setValue(y_pct)
                self.overlay_y_label.setText(f"{y_pct}%")
                opacity_pct = round(overlay.get("opacity", 1.0) * 100)
                self.opacity_slider.setValue(opacity_pct)
                self.opacity_label.setText(f"{opacity_pct}%")
        finally:
            self._updating = False
