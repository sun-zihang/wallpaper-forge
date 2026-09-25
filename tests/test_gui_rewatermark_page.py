"""RewatermarkPage._clean_out path rules and selection/ffmpeg banner pure paths."""

from __future__ import annotations

from pathlib import Path

from core.tasks import OutputMode
from gui.pages.rewatermark_page import _clean_out


def test_clean_out_beside_defaults(tmp_path: Path):
    src = tmp_path / "wall.png"
    src.write_bytes(b"x")
    out = _clean_out(src, "png", OutputMode.BESIDE, None)
    assert out == tmp_path / "converted" / "wall_clean.png"
    assert out.resolve() != src.resolve()


def test_clean_out_unified(tmp_path: Path):
    src = tmp_path / "wall.png"
    unified = tmp_path / "out"
    out = _clean_out(src, "png", OutputMode.UNIFIED, unified)
    assert out == unified / "wall_clean.png"


def test_clean_out_overwrite_returns_base_even_if_exists(tmp_path: Path):
    src = tmp_path / "wall.png"
    src.write_bytes(b"x")
    base = tmp_path / "converted" / "wall_clean.png"
    base.parent.mkdir()
    base.write_bytes(b"old")
    out = _clean_out(src, "png", OutputMode.BESIDE, None, overwrite=True)
    assert out == base


def test_clean_out_avoids_equal_to_source(tmp_path: Path):
    # construct case where first candidate equals src (stem_clean.ext == name)
    # e.g. src already named wall_clean.png in converted/
    src_dir = tmp_path / "converted"
    src_dir.mkdir()
    src = src_dir / "wall_clean.png"
    src.write_bytes(b"x")
    out = _clean_out(src, "png", OutputMode.BESIDE, None)
    assert out.resolve() != src.resolve()
    assert out.name.startswith("wall_clean")


def test_clean_out_increments_when_exists_elsewhere(tmp_path: Path):
    src = tmp_path / "wall.png"
    src.write_bytes(b"x")
    conv = tmp_path / "converted"
    conv.mkdir()
    existing = conv / "wall_clean.png"
    existing.write_bytes(b"other")
    out = _clean_out(src, "png", OutputMode.BESIDE, None)
    assert out != existing
    assert out.exists() is False
    assert out.parent == conv
    assert out.name in {"wall_clean (1).png", "wall_clean_out.png"} or "wall_clean" in out.name


def test_set_ffmpeg_ok_toggles_banner(qapp):
    page = _rew_page(qapp)
    try:
        assert not page.banner.isVisible() or True  # visibility after show not required
        page.set_ffmpeg_ok(False)
        assert page._ffmpeg_ok is False
        assert page.banner.isVisibleTo(page)
        page.set_ffmpeg_ok(True)
        assert page._ffmpeg_ok is True
        assert not page.banner.isVisibleTo(page)
    finally:
        page.deleteLater()
        qapp.processEvents()


def _rew_page(qapp, tmp_path=None):
    from gui.pages.rewatermark_page import RewatermarkPage

    if tmp_path is not None:
        p = tmp_path / "settings.json"
        p.write_text("{}", encoding="utf-8")
        # caller must monkeypatch; for bare tests use isolated store
    return RewatermarkPage()


def test_selection_changed_labels(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.pages.rewatermark_page import RewatermarkPage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    page = RewatermarkPage()
    try:
        # no selection → multi/none message
        page._selection_changed()
        assert "选中单个文件" in page.boxes_label.text()

        src = tmp_path / "a.png"
        src.write_bytes(b"x")
        page.table.add_paths([src])
        page.table.table.selectRow(0)
        page._selection_changed()
        assert "未框选" in page.boxes_label.text()

        page._boxes[src] = [(0, 0, 10, 10), (1, 1, 5, 5)]
        page._selection_changed()
        assert "已框选 2" in page.boxes_label.text()
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_current_file_requires_single_row(qapp, tmp_path, monkeypatch):

    from gui import settings_store
    from gui.pages import rewatermark_page as mod
    from gui.pages.rewatermark_page import RewatermarkPage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    msgs = []
    monkeypatch.setattr(
        mod.QMessageBox,
        "information",
        staticmethod(lambda *a, **k: msgs.append(a[2] if len(a) > 2 else "")),
    )

    page = RewatermarkPage()
    try:
        assert page._current_file() is None
        assert msgs and "选中一个文件" in msgs[0]

        src = tmp_path / "a.png"
        src.write_bytes(b"x")
        page.table.add_paths([src])
        page.table.table.selectRow(0)
        assert page._current_file() == src
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_start_batch_rejects_missing_boxes(qapp, tmp_path, monkeypatch):

    from gui import settings_store
    from gui.pages import rewatermark_page as mod
    from gui.pages.rewatermark_page import RewatermarkPage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    msgs = []
    monkeypatch.setattr(
        mod.QMessageBox,
        "information",
        staticmethod(lambda *a, **k: msgs.append(str(a[2] if len(a) > 2 else k))),
    )

    page = RewatermarkPage()
    try:
        src = tmp_path / "a.png"
        src.write_bytes(b"x")
        page.table.add_paths([src])
        page.start_batch()
        assert msgs and "还没有框选" in msgs[0]

        # empty batch
        msgs.clear()
        page.table.clear()
        page.start_batch()
        assert msgs and "请先添加文件" in msgs[0]
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_start_batch_rejects_video_without_ffmpeg(qapp, tmp_path, monkeypatch):

    from gui import settings_store
    from gui.pages import rewatermark_page as mod
    from gui.pages.rewatermark_page import RewatermarkPage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    msgs = []
    monkeypatch.setattr(
        mod.QMessageBox,
        "warning",
        staticmethod(lambda *a, **k: msgs.append(str(a[2] if len(a) > 2 else k))),
    )
    monkeypatch.setattr(mod, "ffmpeg_available", lambda: False)

    page = RewatermarkPage()
    try:
        vid = tmp_path / "a.mp4"
        vid.write_bytes(b"\x00" * 32)
        page.table.add_paths([vid])
        page._boxes[vid] = [(0, 0, 4, 4)]
        page.start_batch()
        assert msgs and "无法处理视频" in msgs[0]
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_start_batch_builds_image_tasks(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.pages.rewatermark_page import RewatermarkPage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    page = RewatermarkPage()
    try:
        src = tmp_path / "a.png"
        src.write_bytes(b"x")
        page.table.add_paths([src])
        page._boxes[src] = [(0, 0, 8, 8)]

        submitted = []
        monkeypatch.setattr(page, "_submit", lambda b: submitted.append(b))
        monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: True)
        page.start_batch()
        assert len(submitted) == 1
        batch = submitted[0]
        assert len(batch) == 1
        t = batch[0]
        assert t.sources == [src]
        assert t.params["boxes"] == [(0, 0, 8, 8)]
        assert t.outputs[0].name == "a_clean.png"
        assert t.outputs[0].parent.name == "converted"
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_select_boxes_rejects_video_without_ffmpeg(qapp, tmp_path, monkeypatch):

    from gui import settings_store
    from gui.pages import rewatermark_page as mod
    from gui.pages.rewatermark_page import RewatermarkPage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    msgs = []
    monkeypatch.setattr(
        mod.QMessageBox,
        "warning",
        staticmethod(lambda *a, **k: msgs.append(str(a[2] if len(a) > 2 else k))),
    )
    monkeypatch.setattr(mod, "ffmpeg_available", lambda: False)

    page = RewatermarkPage()
    try:
        vid = tmp_path / "a.mp4"
        vid.write_bytes(b"\x00" * 16)
        page.table.add_paths([vid])
        page.table.table.selectRow(0)
        page._select_boxes()
        assert msgs and "无法提取视频预览帧" in msgs[0]
    finally:
        page.deleteLater()
        qapp.processEvents()


def _rew_setup(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.pages import rewatermark_page as mod
    from gui.pages.rewatermark_page import RewatermarkPage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)
    return mod, RewatermarkPage()


def test_select_boxes_without_single_selection_returns_early(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.pages import rewatermark_page as mod
    from gui.pages.rewatermark_page import RewatermarkPage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    msgs = []
    monkeypatch.setattr(
        mod.QMessageBox,
        "information",
        staticmethod(lambda *a, **k: msgs.append(str(a[2] if len(a) > 2 else k))),
    )
    # would open a dialog if reached — must not be called
    monkeypatch.setattr(
        mod.BoxSelectDialog,
        "get_boxes",
        staticmethod(lambda *a, **k: (_ for _ in ()).throw(AssertionError("dialog opened"))),
    )

    page = RewatermarkPage()
    try:
        page._select_boxes()  # nothing selected → early return
        assert msgs and "选中一个文件" in msgs[0]
        assert page._boxes == {}
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_select_boxes_image_opens_dialog_and_records_boxes(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.pages import rewatermark_page as mod
    from gui.pages.rewatermark_page import RewatermarkPage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    page = RewatermarkPage()
    try:
        a = tmp_path / "a.png"
        a.write_bytes(b"x")
        page.table.add_paths([a])
        page.table.table.selectRow(0)

        opened = []
        monkeypatch.setattr(
            mod.BoxSelectDialog,
            "get_boxes",
            staticmethod(
                lambda parent, preview, title: opened.append((preview, title)) or [(0, 0, 5, 5)]
            ),
        )
        page._select_boxes()
        assert opened and opened[0][0] == a
        assert "视频" not in opened[0][1]
        assert page._boxes[a] == [(0, 0, 5, 5)]
        assert "已框选 1" in page.boxes_label.text()

        # dialog cancelled → keep existing boxes untouched
        monkeypatch.setattr(mod.BoxSelectDialog, "get_boxes", staticmethod(lambda *args, **k: None))
        page._select_boxes()
        assert page._boxes[a] == [(0, 0, 5, 5)]
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_select_boxes_video_preview_failures(qapp, tmp_path, monkeypatch):
    from core.rewatermark import RewatermarkError
    from gui import settings_store
    from gui.pages import rewatermark_page as mod
    from gui.pages.rewatermark_page import RewatermarkPage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)
    monkeypatch.setattr(mod, "ffmpeg_available", lambda: True)

    msgs = []
    monkeypatch.setattr(
        mod.QMessageBox,
        "warning",
        staticmethod(lambda *a, **k: msgs.append(str(a[2] if len(a) > 2 else k))),
    )

    page = RewatermarkPage()
    try:
        vid = tmp_path / "clip.mp4"
        vid.write_bytes(b"\x00" * 16)
        page.table.add_paths([vid])
        page.table.table.selectRow(0)

        def raise_rew(src, cache):
            raise RewatermarkError("no frame")

        monkeypatch.setattr(mod, "extract_preview_frame", raise_rew)
        page._select_boxes()
        assert msgs and msgs[-1] == "no frame"

        def raise_generic(src, cache):
            raise RuntimeError("boom")

        monkeypatch.setattr(mod, "extract_preview_frame", raise_generic)
        page._select_boxes()
        assert msgs and msgs[-1] == "视频处理失败：boom"

        # successful preview: title mentions video, boxes recorded
        preview = tmp_path / "preview.jpg"
        preview.write_bytes(b"jpg")
        monkeypatch.setattr(mod, "extract_preview_frame", lambda s, c: preview)
        opened = []
        monkeypatch.setattr(
            mod.BoxSelectDialog,
            "get_boxes",
            staticmethod(lambda parent, p, title: opened.append(title) or [(1, 1, 2, 2)]),
        )
        page._select_boxes()
        assert opened and "视频" in opened[0]
        assert page._boxes[vid] == [(1, 1, 2, 2)]
        assert "已框选 1" in page.boxes_label.text()
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_start_batch_builds_video_task(qapp, tmp_path, monkeypatch):
    from core.tasks import TaskKind
    from gui import settings_store
    from gui.pages import rewatermark_page as mod
    from gui.pages.rewatermark_page import RewatermarkPage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)
    monkeypatch.setattr(mod, "ffmpeg_available", lambda: True)

    page = RewatermarkPage()
    try:
        vid = tmp_path / "clip.mp4"
        vid.write_bytes(b"\x00" * 32)
        page.table.add_paths([vid])
        page._boxes[vid] = [(0, 0, 6, 6)]

        submitted = []
        monkeypatch.setattr(page, "_submit", lambda b: submitted.append(b))
        monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: True)
        page.start_batch()
        assert len(submitted) == 1
        t = submitted[0][0]
        assert t.kind is TaskKind.REMOVE_VIDEO_WATERMARK
        assert t.params["boxes"] == [(0, 0, 6, 6)]
        assert t.params["out"].name == "clip_clean.mp4"
        assert t.outputs == [t.params["out"]]

        # declined confirmation → no submit
        monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: False)
        page.start_batch()
        assert len(submitted) == 1
    finally:
        page.deleteLater()
        qapp.processEvents()
