"""WatermarkDialog / CropDialog pure-path validation (no modal exec)."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog


def test_watermark_dialog_rejects_empty_text(qapp):
    from gui.dialogs import WatermarkDialog

    dlg = WatermarkDialog()
    try:
        dlg.tabs.setCurrentIndex(0)
        dlg.text_edit.setText("   ")
        dlg._accept()
        assert dlg.result() == QDialog.Rejected
        assert dlg.params is None
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_watermark_dialog_accepts_text_and_builds_params(qapp):
    from gui.dialogs import WatermarkDialog

    dlg = WatermarkDialog()
    try:
        dlg.tabs.setCurrentIndex(0)
        dlg.text_edit.setText("我的壁纸")
        dlg.font_size.setValue(48)
        dlg.text_pos.setCurrentIndex(dlg.text_pos.findData("top_left"))
        dlg._accept()
        assert dlg.result() == QDialog.Accepted
        assert dlg.params is not None
        assert dlg.params["op"] == "text_watermark"
        assert dlg.params["text"] == "我的壁纸"
        assert dlg.params["font_size"] == 48
        assert dlg.params["position"] == "top_left"
        r, g, b, a = dlg.params["color"]
        assert (r, g, b) == (255, 255, 255)
        assert 0 <= a <= 255
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_watermark_dialog_image_tab_requires_mark_path(qapp):
    from gui.dialogs import WatermarkDialog

    dlg = WatermarkDialog()
    try:
        dlg.tabs.setCurrentIndex(1)
        dlg.mark_path = None
        dlg._accept()
        assert dlg.result() == QDialog.Rejected
        assert dlg.params is None
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_watermark_dialog_image_tab_rejects_missing_mark_file(qapp, tmp_path):
    from gui.dialogs import WatermarkDialog

    dlg = WatermarkDialog()
    try:
        dlg.tabs.setCurrentIndex(1)
        dlg.mark_path = tmp_path / "gone.png"
        dlg._accept()
        assert dlg.result() == QDialog.Rejected
        assert dlg.params is None
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_watermark_dialog_image_tab_accepts_with_mark_file(qapp, tmp_path):
    from gui.dialogs import WatermarkDialog

    mark = tmp_path / "mark.png"
    mark.write_bytes(b"x")
    dlg = WatermarkDialog()
    try:
        dlg.tabs.setCurrentIndex(1)
        dlg.mark_path = mark
        dlg.mark_scale.setValue(30)
        dlg.mark_pos.setCurrentIndex(dlg.mark_pos.findData("center"))
        dlg._accept()
        assert dlg.result() == QDialog.Accepted
        assert dlg.params is not None
        assert dlg.params["op"] == "image_watermark"
        assert dlg.params["mark"] == mark
        assert dlg.params["scale"] == 0.30
        assert dlg.params["position"] == "center"
        assert 0.0 <= dlg.params["opacity"] <= 1.0
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_crop_get_box_returns_none_for_missing_image(qapp, tmp_path):
    from gui.dialogs import CropDialog

    assert CropDialog.get_box(None, tmp_path / "missing.png") is None


def test_crop_to_image_box_rejects_tiny_selection(qapp, png_64):
    from gui.dialogs import CropDialog

    dlg = CropDialog(png_64)
    try:
        box = dlg._to_image_box((10, 10), (11, 11))
        assert box is None
        # identical points also collapse
        assert dlg._to_image_box((20, 20), (20, 20)) is None
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_crop_accept_without_selection_keeps_rejected(qapp, png_64):
    from gui.dialogs import CropDialog

    dlg = CropDialog(png_64)
    try:
        dlg._origin = None
        dlg._current = None
        dlg.box = None
        dlg._accept()
        assert dlg.result() == QDialog.Rejected
        assert "请先框选裁剪区域" in dlg.info.text()
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def _crop_event(kind, pos, button, buttons):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    if kind == "move":
        kind = QEvent.Type.MouseMove
    return QMouseEvent(kind, QPointF(pos), button, buttons, Qt.NoModifier)


def test_crop_mouse_drag_flow_selects_box(qapp, png_64):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QMouseEvent

    from gui.dialogs import CropDialog

    dlg = CropDialog(png_64)
    try:
        dlg.show()
        qapp.processEvents()
        dlg.resize(420, 340)  # resizeEvent -> _redraw
        qapp.processEvents()
        ox, oy, scaled = dlg._label_geometry()
        ratio_x = scaled.width() / max(1, dlg._pix.width())
        ratio_y = scaled.height() / max(1, dlg._pix.height())

        def canvas_pt(ix, iy):
            return QPoint(ox + int(ix * ratio_x), oy + int(iy * ratio_y))

        start = canvas_pt(8, 8)
        end = canvas_pt(40, 40)
        dlg.mousePressEvent(
            _crop_event(QMouseEvent.Type.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton)
        )
        assert dlg._origin == (start.x(), start.y())
        dlg.mouseMoveEvent(_crop_event("move", end, Qt.NoButton, Qt.LeftButton))
        assert dlg._current == (end.x(), end.y())
        dlg.mouseReleaseEvent(
            _crop_event(QMouseEvent.Type.MouseButtonRelease, end, Qt.LeftButton, Qt.NoButton)
        )
        assert dlg.box is not None
        left, top, right, bottom = dlg.box
        assert right - left >= 2 and bottom - top >= 2
        assert 0 <= left < right <= dlg._pix.width()
        assert 0 <= top < bottom <= dlg._pix.height()
        assert "已选区域" in dlg.info.text()
        assert "像素" in dlg.info.text()
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_crop_right_click_press_is_noop(qapp, png_64):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QMouseEvent

    from gui.dialogs import CropDialog

    dlg = CropDialog(png_64)
    try:
        dlg._origin = None
        dlg.mousePressEvent(
            _crop_event(
                QMouseEvent.Type.MouseButtonPress,
                QPoint(5, 5),
                Qt.RightButton,
                Qt.RightButton,
            )
        )
        assert dlg._origin is None
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_crop_move_without_press_is_noop(qapp, png_64):
    from PySide6.QtCore import QPoint, Qt

    from gui.dialogs import CropDialog

    dlg = CropDialog(png_64)
    try:
        dlg._origin = None
        dlg._current = None
        dlg.mouseMoveEvent(_crop_event("move", QPoint(5, 5), Qt.NoButton, Qt.LeftButton))
        assert dlg._origin is None
        assert dlg._current is None
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_crop_accept_computes_box_from_pending_drag(qapp, png_64):
    from gui.dialogs import CropDialog

    dlg = CropDialog(png_64)
    try:
        ox, oy, scaled = dlg._label_geometry()
        ratio_x = scaled.width() / max(1, dlg._pix.width())
        ratio_y = scaled.height() / max(1, dlg._pix.height())
        dlg._origin = (ox + int(8 * ratio_x), oy + int(8 * ratio_y))
        dlg._current = (ox + int(48 * ratio_x), oy + int(48 * ratio_y))
        dlg.box = None
        dlg._accept()
        assert dlg.result() == QDialog.Accepted
        assert dlg.box is not None
        left, top, right, bottom = dlg.box
        assert right - left >= 2 and bottom - top >= 2
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_crop_get_box_accepted_returns_box(qapp, png_64, monkeypatch):
    from gui.dialogs import CropDialog

    def fake_exec(self):
        self.box = (1, 2, 3, 4)
        return QDialog.Accepted

    monkeypatch.setattr(CropDialog, "exec", fake_exec)
    assert CropDialog.get_box(None, png_64) == (1, 2, 3, 4)


def test_crop_get_box_rejected_returns_none(qapp, png_64, monkeypatch):
    from gui.dialogs import CropDialog

    monkeypatch.setattr(CropDialog, "exec", lambda self: QDialog.Rejected)
    assert CropDialog.get_box(None, png_64) is None


def test_watermark_browse_mark_updates_path(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from gui.dialogs import WatermarkDialog

    mark = tmp_path / "mark.png"
    mark.write_bytes(b"x")
    dlg = WatermarkDialog()
    try:
        monkeypatch.setattr(
            QFileDialog,
            "getOpenFileName",
            staticmethod(lambda *a, **k: (str(mark), "图片 (*.png)")),
        )
        dlg._browse_mark()
        assert dlg.mark_path == mark
        assert dlg.mark_edit.text() == str(mark)

        monkeypatch.setattr(
            QFileDialog,
            "getOpenFileName",
            staticmethod(lambda *a, **k: ("", "")),
        )
        dlg._browse_mark()
        assert dlg.mark_path == mark
        assert dlg.mark_edit.text() == str(mark)
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_watermark_get_params_accepted_and_rejected(qapp, monkeypatch):
    from gui.dialogs import WatermarkDialog

    def fake_exec(self):
        self.params = {"op": "text_watermark", "text": "水印"}
        return QDialog.Accepted

    monkeypatch.setattr(WatermarkDialog, "exec", fake_exec)
    params = WatermarkDialog.get_params(None)
    assert params is not None
    assert params["op"] == "text_watermark"

    monkeypatch.setattr(WatermarkDialog, "exec", lambda self: QDialog.Rejected)
    assert WatermarkDialog.get_params(None) is None
