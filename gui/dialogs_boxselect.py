from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from core.rewatermark import RewatermarkError, validate_boxes
from gui.styles import ACCENT, BG, BORDER


class BoxSelectDialog(QDialog):
    """Rubber-band multi-rectangle selector on a preview image.

    Coordinates returned are in original image pixels (l, t, r, b).
    """

    def __init__(self, image_path: Path, title: str = "框选水印区域", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(860, 600)
        self.image_path = Path(image_path)
        self._pix = QPixmap(str(self.image_path))
        if self._pix.isNull():
            raise RewatermarkError(f"无法预览: {self.image_path.name}")

        self.boxes_img: list[tuple[int, int, int, int]] = []
        self._drag_start: QPoint | None = None
        self._drag_end: QPoint | None = None

        layout = QVBoxLayout(self)
        self.hint = QLabel("按住左键拖拽画框，可画多个；双击已有框可删除。确认后点「确定」。")
        self.hint.setObjectName("mutedText")
        layout.addWidget(self.hint)

        self.canvas = QLabel()
        self.canvas.setAlignment(Qt.AlignCenter)
        self.canvas.setMinimumSize(480, 320)
        self.canvas.setStyleSheet(f"background: {BG}; border: 1px solid {BORDER};")
        layout.addWidget(self.canvas, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("确定")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._geom = (0, 0, 1.0)  # ox, oy, scale
        self._scaled_cache: QPixmap | None = None
        self._scaled_key: tuple[int, int] | None = None
        self._redraw()

    def _layout_metrics(self) -> tuple[int, int, float, int, int]:
        cw = max(self.canvas.width(), 1)
        ch = max(self.canvas.height(), 1)
        scale = min(cw / self._pix.width(), ch / self._pix.height(), 1.0)
        scale = max(scale, 1e-4)
        nw = max(1, int(self._pix.width() * scale))
        nh = max(1, int(self._pix.height() * scale))
        ox = (cw - nw) // 2
        oy = (ch - nh) // 2
        return ox, oy, scale, nw, nh

    def _scaled_pixmap(self, nw: int, nh: int) -> QPixmap:
        key = (nw, nh)
        if self._scaled_cache is None or self._scaled_key != key:
            self._scaled_cache = self._pix.scaled(
                nw, nh, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._scaled_key = key
        return self._scaled_cache

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._redraw()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        pos = event.position().toPoint()
        # double-click delete handled in mouseDoubleClickEvent
        self._drag_start = pos
        self._drag_end = pos
        self._redraw()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is None:
            return
        self._drag_end = event.position().toPoint()
        self._redraw()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton or self._drag_start is None:
            return
        start, end = self._drag_start, self._drag_end or self._drag_start
        self._drag_start = None
        self._drag_end = None
        box = self._to_image_rect(start, end)
        if box is None:
            self._redraw()
            return
        try:
            validate_boxes([box], self._pix.width(), self._pix.height())
        except RewatermarkError as e:
            self.hint.setText(str(e))
            self._redraw()
            return
        self.boxes_img.append(box)
        self.hint.setText(f"已选 {len(self.boxes_img)} 个区域（双击可删除）")
        self._redraw()

    def mouseDoubleClickEvent(self, event) -> None:
        pos = event.position().toPoint()
        img_pt = self._to_image_point(pos)
        if img_pt is None:
            return
        x, y = img_pt
        for i in range(len(self.boxes_img) - 1, -1, -1):
            left, t, r, b = self.boxes_img[i]
            if left <= x <= r and t <= y <= b:
                del self.boxes_img[i]
                self.hint.setText(f"已选 {len(self.boxes_img)} 个区域（双击可删除）")
                self._redraw()
                return

    def _to_image_point(self, canvas_pos: QPoint) -> tuple[int, int] | None:
        ox, oy, scale, nw, nh = self._layout_metrics()
        lx = canvas_pos.x() - ox
        ly = canvas_pos.y() - oy
        if lx < 0 or ly < 0 or lx > nw or ly > nh:
            return None
        x = int(lx / scale)
        y = int(ly / scale)
        x = max(0, min(self._pix.width() - 1, x))
        y = max(0, min(self._pix.height() - 1, y))
        return x, y

    def _to_image_rect(self, a: QPoint, b: QPoint) -> tuple[int, int, int, int] | None:
        pa = self._to_image_point(a)
        pb = self._to_image_point(b)
        if pa is None or pb is None:
            return None
        left, r = sorted((pa[0], pb[0]))
        t, btm = sorted((pa[1], pb[1]))
        if r - left < 2 or btm - t < 2:
            return None
        return (left, t, r, btm)

    def _redraw(self) -> None:
        ox, oy, scale, nw, nh = self._layout_metrics()
        from PySide6.QtGui import QPixmap as QP

        canvas = QP(self.canvas.size())
        canvas.fill(QColor(BG))
        painter = QPainter(canvas)
        scaled = self._scaled_pixmap(nw, nh)
        painter.drawPixmap(ox, oy, scaled)

        pen = QPen(QColor(ACCENT), 2)
        painter.setPen(pen)
        selection = QColor(ACCENT)
        selection.setAlpha(50)
        painter.setBrush(selection)
        for left, t, r, b in self.boxes_img:
            x1 = ox + int(left * scale)
            y1 = oy + int(t * scale)
            w = max(2, int((r - left) * scale))
            h = max(2, int((b - t) * scale))
            painter.drawRect(x1, y1, w, h)

        if self._drag_start and self._drag_end:
            a = self._to_image_rect(self._drag_start, self._drag_end)
            if a:
                left, t, r, b = a
                x1 = ox + int(left * scale)
                y1 = oy + int(t * scale)
                w = max(2, int((r - left) * scale))
                h = max(2, int((b - t) * scale))
                painter.setPen(QColor(ACCENT))
                active = QColor(ACCENT)
                active.setAlpha(60)
                painter.setBrush(active)
                painter.drawRect(x1, y1, w, h)
        painter.end()
        self.canvas.setPixmap(canvas)

    def _accept(self) -> None:
        if not self.boxes_img:
            QMessageBox.information(self, "提示", "请至少框选一个水印区域")
            return
        self.accept()

    @staticmethod
    def get_boxes(
        parent, image_path: Path, title: str = "框选水印区域"
    ) -> list[tuple[int, int, int, int]] | None:
        try:
            dlg = BoxSelectDialog(image_path, title, parent)
        except RewatermarkError:
            return None
        if dlg.exec() == QDialog.Accepted:
            return list(dlg.boxes_img)
        return None
