from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPixmap, QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from core.annotate import ImageOpError


class CropDialog(QDialog):
    """Rubber-band crop on a scaled image preview."""

    def __init__(self, image_path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("裁剪")
        self.resize(720, 520)
        self.image_path = Path(image_path)
        self._pix = QPixmap(str(self.image_path))
        if self._pix.isNull():
            raise ImageOpError(f"无法预览图片: {self.image_path.name}")
        self._origin: tuple[int, int] | None = None
        self._current: tuple[int, int] | None = None
        self.box: tuple[int, int, int, int] | None = None

        layout = QVBoxLayout(self)
        self.canvas = QLabel()
        self.canvas.setAlignment(Qt.AlignCenter)
        self.canvas.setMinimumSize(400, 300)
        self.canvas.setStyleSheet("background: #111; border: 1px solid #3c3c3c;")
        layout.addWidget(self.canvas, 1)

        self.info = QLabel("在图片上按住鼠标左键拖拽选择区域")
        self.info.setStyleSheet("color: #888;")
        layout.addWidget(self.info)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("确定")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._scale = 1.0
        self._redraw()

    def _fit(self, w: int, h: int) -> tuple[QPixmap, float, int, int]:
        available = self.canvas.size()
        scale = min(available.width() / self._pix.width(), available.height() / self._pix.height(), 1.0)
        scale = max(scale, 0.01)
        nw = max(1, int(self._pix.width() * scale))
        nh = max(1, int(self._pix.height() * scale))
        scaled = self._pix.scaled(nw, nh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return scaled, scale, nw, nh

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._redraw()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        pos = event.position().toPoint()
        self._origin = (pos.x(), pos.y())
        self._current = self._origin
        self._redraw()

    def mouseMoveEvent(self, event) -> None:
        if self._origin is None:
            return
        pos = event.position().toPoint()
        self._current = (pos.x(), pos.y())
        self._redraw()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._origin and self._current:
            self.box = self._to_image_box(self._origin, self._current)
            if self.box:
                l, t, r, b = self.box
                self.info.setText(f"已选区域：{r - l} × {b - t} 像素")
        self._redraw()

    def _label_geometry(self) -> tuple[int, int, QPixmap]:
        scaled, scale, nw, nh = self._fit(self.width(), self.height())
        # account for info/buttons roughly: use canvas size
        cw = max(self.canvas.width(), 1)
        ch = max(self.canvas.height(), 1)
        scaled2, scale, nw, nh = self._fit(cw, ch)
        ox = (cw - nw) // 2
        oy = (ch - nh) // 2
        return ox, oy, scaled2

    def _to_image_box(self, a: tuple[int, int], b: tuple[int, int]):
        ox, oy, scaled = self._label_geometry()
        x1, y1 = a
        x2, y2 = b
        # coords relative to canvas; image starts at ox,oy inside label — we paint on canvas via pixmap
        # Simpler: treat label content coordinates with offset
        lx1, ly1 = x1 - ox, y1 - oy
        lx2, ly2 = x2 - ox, y2 - oy
        scale_x = self._pix.width() / max(scaled.width(), 1)
        scale_y = self._pix.height() / max(scaled.height(), 1)
        left = int(max(0, min(lx1, lx2) * scale_x))
        top = int(max(0, min(ly1, ly2) * scale_y))
        right = int(min(self._pix.width(), max(lx1, lx2) * scale_x))
        bottom = int(min(self._pix.height(), max(ly1, ly2) * scale_y))
        if right - left < 2 or bottom - top < 2:
            return None
        return (left, top, right, bottom)

    def _redraw(self) -> None:
        ox, oy, scaled = self._label_geometry()
        canvas = QPixmap(self.canvas.size())
        canvas.fill(QColor("#111111"))
        painter = QPainter(canvas)
        painter.drawPixmap(ox, oy, scaled)
        if self._origin and self._current:
            x1, y1 = self._origin
            x2, y2 = self._current
            rect = (
                min(x1, x2),
                min(y1, y2),
                abs(x2 - x1),
                abs(y2 - y1),
            )
            painter.setPen(QColor("#3b82f6"))
            painter.setBrush(QColor(59, 130, 246, 60))
            painter.drawRect(*rect)
        painter.end()
        self.canvas.setPixmap(canvas)

    def _accept(self) -> None:
        if self.box is None and self._origin and self._current:
            self.box = self._to_image_box(self._origin, self._current)
        if self.box is None:
            self.info.setText("请先框选裁剪区域")
            return
        self.accept()

    @staticmethod
    def get_box(parent, image_path: Path) -> tuple[int, int, int, int] | None:
        try:
            dlg = CropDialog(image_path, parent)
        except ImageOpError:
            return None
        if dlg.exec() == QDialog.Accepted:
            return dlg.box
        return None


class WatermarkDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("水印")
        self.resize(480, 360)
        self.params: dict | None = None
        self.mark_path: Path | None = None

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # text tab
        text_tab = QWidget()
        g = QGridLayout(text_tab)
        g.addWidget(QLabel("文字内容"), 0, 0)
        self.text_edit = QLineEdit("我的壁纸")
        g.addWidget(self.text_edit, 0, 1)
        g.addWidget(QLabel("字号"), 1, 0)
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 200)
        self.font_size.setValue(32)
        g.addWidget(self.font_size, 1, 1)
        g.addWidget(QLabel("透明度"), 2, 0)
        self.text_opacity = QSlider(Qt.Horizontal)
        self.text_opacity.setRange(10, 100)
        self.text_opacity.setValue(70)
        g.addWidget(self.text_opacity, 2, 1)
        g.addWidget(QLabel("位置"), 3, 0)
        self.text_pos = self._pos_combo()
        g.addWidget(self.text_pos, 3, 1)
        tabs.addTab(text_tab, "文字水印")

        # image tab
        img_tab = QWidget()
        g2 = QGridLayout(img_tab)
        g2.addWidget(QLabel("水印图片"), 0, 0)
        self.mark_edit = QLineEdit()
        self.mark_edit.setReadOnly(True)
        g2.addWidget(self.mark_edit, 0, 1)
        browse = QPushButton("选择…")
        browse.setObjectName("secondary")
        browse.clicked.connect(self._browse_mark)
        g2.addWidget(browse, 0, 2)
        g2.addWidget(QLabel("相对宽度"), 1, 0)
        self.mark_scale = QSlider(Qt.Horizontal)
        self.mark_scale.setRange(5, 100)
        self.mark_scale.setValue(20)
        g2.addWidget(self.mark_scale, 1, 1, 1, 2)
        g2.addWidget(QLabel("透明度"), 2, 0)
        self.mark_opacity = QSlider(Qt.Horizontal)
        self.mark_opacity.setRange(10, 100)
        self.mark_opacity.setValue(80)
        g2.addWidget(self.mark_opacity, 2, 1, 1, 2)
        g2.addWidget(QLabel("位置"), 3, 0)
        self.mark_pos = self._pos_combo()
        g2.addWidget(self.mark_pos, 3, 1, 1, 2)
        tabs.addTab(img_tab, "图片水印")

        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("确定")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.tabs = tabs

    @staticmethod
    def _pos_combo() -> QComboBox:
        c = QComboBox()
        for label, val in [
            ("右下", "bottom_right"),
            ("右上", "top_right"),
            ("左下", "bottom_left"),
            ("左上", "top_left"),
            ("居中", "center"),
        ]:
            c.addItem(label, val)
        return c

    def _browse_mark(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择水印图片", "", "图片 (*.png *.jpg *.webp *.bmp)"
        )
        if path:
            self.mark_path = Path(path)
            self.mark_edit.setText(path)

    def _accept(self) -> None:
        if self.tabs.currentIndex() == 0:
            text = self.text_edit.text().strip()
            if not text:
                return
            self.params = {
                "op": "text_watermark",
                "text": text,
                "font_size": self.font_size.value(),
                "color": (255, 255, 255, int(self.text_opacity.value() * 2.55)),
                "position": self.text_pos.currentData(),
            }
        else:
            if not self.mark_path or not self.mark_path.is_file():
                return
            self.params = {
                "op": "image_watermark",
                "mark": self.mark_path,
                "scale": self.mark_scale.value() / 100,
                "opacity": self.mark_opacity.value() / 100,
                "position": self.mark_pos.currentData(),
            }
        self.accept()

    @staticmethod
    def get_params(parent) -> dict | None:
        dlg = WatermarkDialog(parent)
        if dlg.exec() == QDialog.Accepted:
            return dlg.params
        return None
