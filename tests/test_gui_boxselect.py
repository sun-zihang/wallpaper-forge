"""BoxSelectDialog pure-path validation (no modal exec)."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QDialog, QMessageBox


def test_box_select_missing_image_raises(qapp, tmp_path):
    from gui.dialogs_boxselect import BoxSelectDialog
    from core.rewatermark import RewatermarkError

    try:
        BoxSelectDialog(tmp_path / "missing.png")
    except RewatermarkError as exc:
        assert "无法预览" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RewatermarkError")


def test_box_select_get_boxes_returns_none_for_missing_image(qapp, tmp_path):
    from gui.dialogs_boxselect import BoxSelectDialog

    assert BoxSelectDialog.get_boxes(None, tmp_path / "missing.png") is None


def test_box_select_accept_without_boxes_keeps_rejected(qapp, png_64, monkeypatch):
    from gui.dialogs_boxselect import BoxSelectDialog

    infos = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        staticmethod(lambda *args: infos.append(args)),
    )
    dlg = BoxSelectDialog(png_64)
    try:
        dlg.boxes_img = []
        dlg._accept()
        assert dlg.result() == QDialog.Rejected
        assert infos
        assert "请至少框选一个水印区域" in infos[0][2]
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_box_select_accept_with_boxes(qapp, png_64):
    from gui.dialogs_boxselect import BoxSelectDialog

    dlg = BoxSelectDialog(png_64)
    try:
        dlg.boxes_img = [(4, 4, 20, 20)]
        dlg._accept()
        assert dlg.result() == QDialog.Accepted
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_box_select_to_image_rect_rejects_tiny_drag(qapp, png_64):
    from gui.dialogs_boxselect import BoxSelectDialog

    dlg = BoxSelectDialog(png_64)
    try:
        # identical points → span < 2
        assert dlg._to_image_rect(QPoint(10, 10), QPoint(10, 10)) is None
        # map image-space corners through layout metrics for a valid positive drag
        ox, oy, scale, nw, nh = dlg._layout_metrics()
        a = QPoint(ox + int(4 * scale), oy + int(4 * scale))
        b = QPoint(ox + int(40 * scale), oy + int(40 * scale))
        box = dlg._to_image_rect(a, b)
        assert box is not None
        l, t, r, btm = box
        assert r - l >= 2 and btm - t >= 2
        assert 0 <= l < r <= dlg._pix.width()
        assert 0 <= t < btm <= dlg._pix.height()
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_box_select_mouse_release_appends_valid_box(qapp, png_64):
    from gui.dialogs_boxselect import BoxSelectDialog

    dlg = BoxSelectDialog(png_64)
    try:
        ox, oy, scale, nw, nh = dlg._layout_metrics()
        start = QPoint(ox + int(4 * scale), oy + int(4 * scale))
        end = QPoint(ox + int(40 * scale), oy + int(40 * scale))
        box = dlg._to_image_rect(start, end)
        assert box is not None
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            end.toPointF(),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        # Prime the drag state as mousePressEvent would.
        dlg._drag_start = start
        dlg._drag_end = end
        dlg.mouseReleaseEvent(event)
        assert box in dlg.boxes_img
        assert f"已选 {len(dlg.boxes_img)} 个区域" in dlg.hint.text()
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_box_select_double_click_deletes_box(qapp, png_64):
    from PySide6.QtCore import QPointF

    from gui.dialogs_boxselect import BoxSelectDialog

    dlg = BoxSelectDialog(png_64)
    try:
        box = (4, 4, 30, 30)
        dlg.boxes_img = [box]
        # map image coords → canvas coords via layout metrics
        ox, oy, scale, nw, nh = dlg._layout_metrics()
        cx = ox + int(((box[0] + box[2]) // 2) * scale)
        cy = oy + int(((box[1] + box[3]) // 2) * scale)
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonDblClick,
            QPointF(cx, cy),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        dlg.mouseDoubleClickEvent(event)
        assert dlg.boxes_img == []
        assert "已选 0 个区域" in dlg.hint.text()
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_box_select_double_click_outside_image_is_noop(qapp, png_64):
    from PySide6.QtCore import QPointF

    from gui.dialogs_boxselect import BoxSelectDialog

    dlg = BoxSelectDialog(png_64)
    try:
        dlg.boxes_img = [(4, 4, 30, 30)]
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonDblClick,
            QPointF(-10, -10),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        dlg.mouseDoubleClickEvent(event)
        assert len(dlg.boxes_img) == 1
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_box_select_to_image_point_clamps_and_rejects_outside(qapp, png_64):
    from gui.dialogs_boxselect import BoxSelectDialog

    dlg = BoxSelectDialog(png_64)
    try:
        ox, oy, scale, nw, nh = dlg._layout_metrics()
        # outside left/top of scaled image
        assert dlg._to_image_point(QPoint(ox - 5, oy + 5)) is None
        assert dlg._to_image_point(QPoint(ox + 5, oy - 5)) is None
        # inside → clamped into image bounds
        pt = dlg._to_image_point(QPoint(ox, oy))
        assert pt is not None
        assert 0 <= pt[0] < dlg._pix.width()
        assert 0 <= pt[1] < dlg._pix.height()
        # far bottom-right of canvas beyond scaled image
        assert dlg._to_image_point(QPoint(ox + nw + 50, oy + nh + 50)) is None
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()
