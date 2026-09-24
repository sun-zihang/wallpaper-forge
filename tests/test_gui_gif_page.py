"""GifPage mode sync, start_batch guards, and merge/split task building."""

from __future__ import annotations

from pathlib import Path


def _page(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.pages.gif_page import GifPage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)
    return GifPage()


def test_sync_mode_toggles_visibility_and_accept_exts(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        # default split
        assert page.mode.currentData() == "split"
        assert page.start_btn.text() == "开始拆帧"
        assert not page.lbl_dur.isVisibleTo(page)
        assert page.lbl_step.isVisibleTo(page)
        assert set(page.table.accept_exts) == {".gif"}

        page.mode.setCurrentIndex(1)  # merge
        assert page.mode.currentData() == "merge"
        assert page.start_btn.text() == "开始合帧"
        assert page.lbl_dur.isVisibleTo(page)
        assert not page.lbl_step.isVisibleTo(page)
        assert page.table.accept_exts == {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".bmp",
            ".gif",
        }

        # loop defaults checked; reverse not
        assert page.loop.isChecked()
        assert not page.reverse.isChecked()
        assert page.step.value() == 1
        assert page.dur.value() == 100
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_split_empty_shows_message(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    page = _page(qapp, tmp_path, monkeypatch)
    msgs = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        staticmethod(lambda *a, **k: msgs.append(str(a[2] if len(a) > 2 else k))),
    )
    try:
        page.start_batch()
        assert msgs and "请先添加 GIF" in msgs[0]
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_split_builds_tasks_with_taken_out_dirs(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        g1 = tmp_path / "a.gif"
        g2 = tmp_path / "b.gif"
        g1.write_bytes(b"GIF89a")
        g2.write_bytes(b"GIF89a")
        page.table.add_paths([g1, g2])
        page.step.setValue(3)

        submitted = []
        monkeypatch.setattr(page, "_submit", lambda b: submitted.append(b))
        monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: True)
        page.start_batch()
        assert len(submitted) == 1
        batch = submitted[0]
        assert len(batch) == 2
        assert batch[0].kind.name == "GIF_SPLIT"
        assert batch[0].params["step"] == 3
        d0 = batch[0].params["out_dir"]
        d1 = batch[1].params["out_dir"]
        assert d0 != d1
        assert "frames" in d0.name or d0.name.endswith("_frames")
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_merge_empty_and_single_gif_messages(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    page = _page(qapp, tmp_path, monkeypatch)
    msgs = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        staticmethod(lambda *a, **k: msgs.append(str(a[2] if len(a) > 2 else k))),
    )
    try:
        page.mode.setCurrentIndex(1)
        page.start_batch()
        assert msgs and "请先添加图片序列" in msgs[0]

        only = tmp_path / "solo.gif"
        only.write_bytes(b"GIF89a")
        page.table.add_paths([only])
        msgs.clear()
        page.start_batch()
        assert msgs and "合帧需要多张图片" in msgs[0]
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_merge_builds_task_from_sorted_frames(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        page.mode.setCurrentIndex(1)
        b = tmp_path / "b.png"
        a = tmp_path / "a.png"
        b.write_bytes(b"x")
        a.write_bytes(b"x")
        # add out of order; merge should sort by name
        page.table.add_paths([b, a])
        page.dur.setValue(80)
        page.loop.setChecked(False)
        page.reverse.setChecked(True)

        submitted = []
        monkeypatch.setattr(page, "_submit", lambda lambda_b: submitted.append(lambda_b))
        monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: True)
        page.start_batch()
        assert len(submitted) == 1
        t = submitted[0][0]
        assert t.sources == [a, b]
        assert t.params["duration_ms"] == 80
        assert t.params["loop"] == 1  # not infinite
        assert t.params["reverse"] is True
        assert t.outputs[0].suffix == ".gif"
        assert t.outputs[0].stem == a.stem
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_split_declined_overwrite_does_not_submit(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        g = tmp_path / "a.gif"
        g.write_bytes(b"GIF89a")
        page.table.add_paths([g])
        submitted = []
        monkeypatch.setattr(page, "_submit", lambda b: submitted.append(b))
        monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: False)
        page.start_batch()
        assert submitted == []
    finally:
        page.deleteLater()
        qapp.processEvents()
