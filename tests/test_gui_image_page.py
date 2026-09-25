"""ImagePage option persistence, apply_settings clamps, and start_batch guards."""

from __future__ import annotations


def test_apply_settings_clamps_quality_and_ignores_bad_fmt(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.pages.image_page import ImagePage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    page = ImagePage()
    try:
        page.apply_settings({"last_image_format": "NOT_A_FMT", "default_quality": "bad"})
        assert page.fmt.currentText() == "JPG"  # invalid fmt ignored
        assert page.quality.value() == 90
        assert page.quality_label.text() == "90"

        page.apply_settings({"last_image_format": "WebP", "default_quality": 250})
        assert page.fmt.currentText() == "WebP"
        assert page.quality.value() == 100
        assert page.quality_label.text() == "100"

        page.apply_settings({"default_quality": 0})
        assert page.quality.value() == 1
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_format_change_persists_and_quality_label_tracks(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.pages.image_page import ImagePage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    page = ImagePage()
    try:
        page.fmt.setCurrentText("BMP")
        assert settings_store.load_settings()["last_image_format"] == "BMP"

        page.quality.setValue(42)
        assert page.quality_label.text() == "42"

        page.scale_enable.setChecked(True)
        assert page.scale_w.isEnabled()
        page.scale_enable.setChecked(False)
        assert not page.scale_w.isEnabled()
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_start_batch_empty_paths_shows_message(qapp, tmp_path, monkeypatch):

    from gui import settings_store
    from gui.pages import image_page as mod
    from gui.pages.image_page import ImagePage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    msgs = []
    monkeypatch.setattr(
        mod.QMessageBox
        if hasattr(mod, "QMessageBox")
        else __import__("PySide6.QtWidgets", fromlist=["QMessageBox"]).QMessageBox,
        "information",
        staticmethod(lambda *a, **k: msgs.append(str(a[2] if len(a) > 2 else k))),
    )
    # start_batch imports QMessageBox locally — patch the class method
    monkeypatch.setattr(
        __import__("PySide6.QtWidgets", fromlist=["QMessageBox"]).QMessageBox,
        "information",
        staticmethod(lambda *a, **k: msgs.append(str(a[2] if len(a) > 2 else k))),
    )

    page = ImagePage()
    try:
        page.start_batch()
        assert msgs and "请先添加图片" in msgs[0]
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_crop_watermark_empty_selection_messages(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from gui import settings_store
    from gui.pages.image_page import ImagePage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    msgs = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        staticmethod(lambda *a, **k: msgs.append(str(a[2] if len(a) > 2 else k))),
    )

    page = ImagePage()
    try:
        page._crop()
        assert msgs and "请先选中一张图片" in msgs[0]
        msgs.clear()
        page._watermark()
        assert msgs and "请先添加并选中图片" in msgs[0]
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_start_batch_submits_convert_task(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.pages.image_page import ImagePage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    page = ImagePage()
    try:
        src = tmp_path / "a.png"
        src.write_bytes(b"x")
        page.table.add_paths([src])
        page.fmt.setCurrentText("WebP")
        page.quality.setValue(70)
        page.scale_enable.setChecked(True)
        page.scale_w.setValue(800)

        submitted = []
        monkeypatch.setattr(page, "_submit", lambda b: submitted.append(b))
        monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: True)
        page.start_batch()
        assert len(submitted) == 1
        t = submitted[0][0]
        assert t.sources == [src]
        assert t.params["quality"] == 70
        assert t.params["max_width"] == 800
        assert t.outputs[0].suffix == ".webp"
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_crop_status_uses_first_of_multi_selection(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.dialogs import CropDialog
    from gui.pages.image_page import ImagePage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    page = ImagePage()
    try:
        a = tmp_path / "a.png"
        b = tmp_path / "b.png"
        a.write_bytes(b"x")
        b.write_bytes(b"y")
        page.table.add_paths([a, b])

        statuses = []
        monkeypatch.setattr(page, "_on_status", lambda t: statuses.append(t))
        # cancel dialog immediately
        monkeypatch.setattr(CropDialog, "get_box", staticmethod(lambda *args, **k: None))
        page._crop()
        assert statuses and "a.png" in statuses[0]
        assert "裁剪使用第一个选中文件" in statuses[0]
    finally:
        page.deleteLater()
        qapp.processEvents()


def _img_page(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.pages.image_page import ImagePage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)
    return ImagePage()


def test_crop_builds_image_edit_task(qapp, tmp_path, monkeypatch):
    from core.tasks import TaskKind
    from gui.dialogs import CropDialog

    page = _img_page(qapp, tmp_path, monkeypatch)
    try:
        src = tmp_path / "photo.png"
        src.write_bytes(b"x")
        page.table.add_paths([src])
        page.table.table.selectRow(0)
        monkeypatch.setattr(CropDialog, "get_box", staticmethod(lambda *a, **k: (1, 2, 30, 40)))
        submitted = []
        monkeypatch.setattr(page, "_submit", lambda b: submitted.append(b))
        monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: True)
        page._crop()
        assert len(submitted) == 1
        t = submitted[0][0]
        assert t.kind is TaskKind.IMAGE_EDIT
        assert t.params == {"op": "crop", "box": (1, 2, 30, 40)}
        assert t.outputs[0].suffix == ".png"
        assert t.outputs[0] != src
        assert t.outputs[0].parent.name == "converted"

        # declined overwrite confirmation must not submit
        monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: False)
        page._crop()
        assert len(submitted) == 1
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_watermark_builds_image_edit_task_for_all_files(qapp, tmp_path, monkeypatch):
    from core.tasks import TaskKind
    from gui.dialogs import WatermarkDialog

    page = _img_page(qapp, tmp_path, monkeypatch)
    try:
        a = tmp_path / "a.png"
        b = tmp_path / "b.png"
        a.write_bytes(b"x")
        b.write_bytes(b"y")
        page.table.add_paths([a, b])

        statuses = []
        monkeypatch.setattr(page, "_on_status", lambda t: statuses.append(t))
        monkeypatch.setattr(
            WatermarkDialog,
            "get_params",
            staticmethod(lambda *args, **k: {"text": "hi", "position": "bottom_right"}),
        )
        submitted = []
        monkeypatch.setattr(page, "_submit", lambda batch: submitted.append(batch))
        monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: True)
        page._watermark()
        assert statuses and "水印将处理 2 个文件" in statuses[0]
        assert len(submitted) == 1
        t = submitted[0][0]
        assert t.kind is TaskKind.IMAGE_EDIT
        assert t.params["text"] == "hi"
        assert t.sources == [a, b]
        assert all(o.suffix == ".png" for o in t.outputs)

        # cancelled dialog → no task; declined confirmation → no task
        monkeypatch.setattr(WatermarkDialog, "get_params", staticmethod(lambda *a, **k: None))
        page._watermark()
        assert len(submitted) == 1
        monkeypatch.setattr(
            WatermarkDialog,
            "get_params",
            staticmethod(lambda *a, **k: {"text": "x", "position": "center"}),
        )
        monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: False)
        page._watermark()
        assert len(submitted) == 1
    finally:
        page.deleteLater()
        qapp.processEvents()
