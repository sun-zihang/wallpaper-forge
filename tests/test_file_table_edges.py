"""FileTable edge branches: preview guards, stat failures, drag-drop, fallback scans."""

from __future__ import annotations

from pathlib import Path


def test_preview_image_fit_returns_on_null_pixmap(qapp):
    from PySide6.QtGui import QPixmap

    from gui.widgets.file_table import _PreviewImage

    w = _PreviewImage(QPixmap())  # null source → early return in _fit
    try:
        assert w._source.isNull()
    finally:
        w.deleteLater()
        qapp.processEvents()


def test_preview_movie_fit_guards(qapp):
    from PySide6.QtGui import QMovie

    from gui.widgets.file_table import _PreviewMovie

    movie = QMovie()  # no source → currentImage is null
    w = _PreviewMovie(movie)
    try:
        w.setMinimumSize(0, 0)
        w.resize(0, 0)
        w._fit()  # width/height 0 → early return
        w.setMinimumSize(320, 240)
        w.resize(320, 240)
        w._fit()  # sized, but frame is null → early return before QPixmap
        assert w._movie.currentImage().isNull()
    finally:
        w.deleteLater()
        qapp.processEvents()


def test_image_preview_dialog_rejects_unpreviewable_file(qapp, tmp_path):
    from gui.widgets.file_table import ImagePreviewDialog

    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not a real png")
    try:
        ImagePreviewDialog(broken)
    except ValueError as e:
        assert "无法预览图片" in str(e)
        assert "broken.png" in str(e)
    else:  # pragma: no cover - failure guard
        raise AssertionError("expected ValueError")


def test_key_falls_back_when_resolve_fails(qapp, tmp_path, monkeypatch):
    from gui.widgets.file_table import FileTable

    def boom(self):
        raise OSError("resolve unavailable")

    monkeypatch.setattr(Path, "resolve", boom)
    p = tmp_path / "a.png"
    assert FileTable._key(p) == str(p)


def test_append_skips_duplicates_and_survives_stat_failure(qapp, tmp_path, monkeypatch):
    from gui.widgets.file_table import FileTable

    table = FileTable()
    try:
        p = tmp_path / "a.png"
        p.write_bytes(b"x")
        table.add_paths([p])
        table.add_paths([p])  # duplicate key → _append returns False
        assert table.table.rowCount() == 1

        real_stat = Path.stat
        calls = {"n": 0}

        def flaky(self, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] >= 3:  # is_dir, is_file pass; _append's stat fails
                raise OSError("vanished")
            return real_stat(self, *args, **kwargs)

        monkeypatch.setattr(Path, "stat", flaky)
        q = tmp_path / "b.png"
        q.write_bytes(b"x")
        table.add_paths([q])
        monkeypatch.setattr(Path, "stat", real_stat)
        assert table.table.rowCount() == 2
        # size column falls back to 0 KB formatting
        assert table.table.item(1, 2).text() in {"0 KB", "0 MB"}
    finally:
        table.deleteLater()
        qapp.processEvents()


def test_type_filter_classifies_package_then_becomes_unknown(qapp, tmp_path):
    from gui.widgets.file_table import FileTable

    table = FileTable(accept_exts={".tga"})
    try:
        p = tmp_path / "a.tga"
        p.write_bytes(b"x")
        table.add_paths([p])
        assert table._type_for_path(p) == "package"
        pkg_idx = table.type_filter.findData("package")
        table.type_filter.setCurrentIndex(pkg_idx)
        assert not table.table.isRowHidden(0)
        table.set_accept_exts({".png"})  # .tga no longer accepted → unknown type
        assert table._type_for_path(p) == ""
        assert table.table.isRowHidden(0)
    finally:
        table.deleteLater()
        qapp.processEvents()


def test_matches_filters_false_for_rows_without_items(qapp):
    from gui.widgets.file_table import FileTable

    table = FileTable()
    try:
        table.table.insertRow(0)  # bare row: no path/status items
        assert table._matches_filters(0, "", "all", "all") is False
    finally:
        table.deleteLater()
        qapp.processEvents()


def test_preview_selected_guards_and_reopens(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QMessageBox

    from gui.widgets.file_table import FileTable

    table = FileTable()
    try:
        # nothing selected → early return
        table.preview_selected()

        good = tmp_path / "ok.png"
        img = QImage(8, 8, QImage.Format_RGBA8888)
        img.fill(Qt.red)
        assert img.save(str(good))
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"garbage")
        table.add_paths([good, bad])

        msgs = []
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            staticmethod(lambda *a, **k: msgs.append(str(a[2] if len(a) > 2 else k))),
        )

        # corrupt image → ImagePreviewDialog raises → warning path
        table.table.selectRow(1)
        table._selection_changed()
        table.preview_selected()
        assert msgs and "无法预览图片" in msgs[0] and "bad.png" in msgs[0]

        # valid image → dialog opens; second call closes the previous one
        table.table.selectRow(0)
        table._selection_changed()
        table.preview_selected()
        first = table._preview_dialog
        assert first is not None
        table.preview_selected()
        second = table._preview_dialog
        assert second is not None and second is not first
        second.close()
        table.preview_selected()
        if table._preview_dialog is not None:
            table._preview_dialog.close()
    finally:
        table.deleteLater()
        qapp.processEvents()


def test_thumbnail_key_stat_failure_returns_epoch(qapp, tmp_path, monkeypatch):
    from gui.widgets.file_table import FileTable

    def boom(self, *args, **kwargs):
        raise OSError("gone")

    table = FileTable()
    try:
        monkeypatch.setattr(Path, "stat", boom)
        assert table._thumbnail_key(tmp_path / "a.png")[1] == 0
    finally:
        monkeypatch.undo()
        table.deleteLater()
        qapp.processEvents()


def test_load_visible_thumbnails_runs_when_shown(qapp, tmp_path):
    from gui.widgets.file_table import FileTable

    table = FileTable()
    try:
        png = tmp_path / "a.png"
        png.write_bytes(b"x")
        vid = tmp_path / "b.mp4"
        vid.write_bytes(b"x")
        table.add_paths([png, vid])

        table.show()
        qapp.processEvents()
        table._load_visible_thumbnails()  # visible viewport → real pass
        # video row hits the non-image continue; png row gets a thumbnail key
        assert table._thumbnail_row_keys.get(0) is not None

        # all rows hidden via search → indexAt returns -1 → top clamps to 0
        table.search_edit.setText("no-such-file")
        assert all(table.table.isRowHidden(r) for r in range(table.table.rowCount()))
        table._load_visible_thumbnails()

        # bare row without a path item → continue inside the scan
        table.search_edit.setText("")
        table.table.insertRow(table.table.rowCount())
        table._load_visible_thumbnails()
    finally:
        table.deleteLater()
        qapp.processEvents()


def test_set_status_falls_back_to_linear_scan(qapp, tmp_path):
    from gui.widgets.file_table import FileTable

    table = FileTable()
    try:
        p = tmp_path / "a.png"
        p.write_bytes(b"x")
        table.add_paths([p])
        table._row_by_key.clear()  # force the by-text fallback branch
        table.set_status_for_path(p, "failed", "boom")
        status = table.table.item(0, 3)
        assert status.text() == "失败（boom）"
        assert status.data(0x0100) == "failed"  # Qt.UserRole
        # unknown path → scan finds nothing → no crash
        table.set_status_for_path(tmp_path / "missing.png", "done")
    finally:
        table.deleteLater()
        qapp.processEvents()


def test_write_status_and_open_output_guards(qapp, tmp_path):
    from gui.widgets.file_table import FileTable

    table = FileTable()
    try:
        table.table.insertRow(0)  # no status item → _write_status returns
        table._write_status(0, "done")
        assert table.table.item(0, 3) is None

        emitted = []
        table.open_output_requested.connect(emitted.append)
        table._selection_rows = set()  # no rows → early return
        table._open_output()
        assert emitted == []
        table._selection_rows = {0}  # row exists but has no item → early return
        table._open_output()
        assert emitted == []
    finally:
        table.deleteLater()
        qapp.processEvents()


def test_drag_enter_and_drop_events(qapp, tmp_path):
    from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
    from PySide6.QtGui import QDragEnterEvent, QDropEvent

    from gui.widgets.file_table import FileTable

    table = FileTable()
    try:
        p = tmp_path / "dragged.png"
        p.write_bytes(b"x")
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(p)), QUrl("http://example.com/x.png")])

        enter = QDragEnterEvent(QPoint(0, 0), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        table.dragEnterEvent(enter)
        assert enter.isAccepted()

        drop = QDropEvent(QPoint(0, 0), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        table.dropEvent(drop)
        assert table.table.rowCount() == 1  # remote url skipped
        assert table.all_paths() == [p]

        # drop with no local files → nothing added, still accepted
        empty_mime = QMimeData()
        empty_mime.setUrls([QUrl("http://example.com/y.png")])
        drop2 = QDropEvent(QPoint(0, 0), Qt.CopyAction, empty_mime, Qt.LeftButton, Qt.NoModifier)
        table.dropEvent(drop2)
        assert table.table.rowCount() == 1
    finally:
        table.deleteLater()
        qapp.processEvents()
