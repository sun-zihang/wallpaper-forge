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
