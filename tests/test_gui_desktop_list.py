from __future__ import annotations


def _close_table(table, qapp):
    table.close()
    table.deleteLater()
    qapp.processEvents()


def _make_table(qapp, tmp_path, names):
    from gui.widgets.file_table import FileTable

    table = FileTable({".png", ".jpg", ".mp4", ".gif", ".pkg"})
    paths = []
    for name in names:
        path = tmp_path / name
        path.write_bytes(b"test")
        paths.append(path)
    table.add_paths(paths)
    return table, paths


def _window(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.main_window import MainWindow

    settings_path = tmp_path / "settings.json"
    settings_path.write_text('{"auto_check_update": false}', encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)
    window = MainWindow("0.0.0-test")
    return window


def test_search_filter_matches_case_insensitive_substring(qapp, tmp_path):
    table, _paths = _make_table(qapp, tmp_path, ("Alpha.png", "beta.mp4", "Gamma.jpg"))
    try:
        table.search_edit.setText("alpha")
        assert [r for r in range(3) if not table.table.isRowHidden(r)] == [0]
        table.search_edit.setText("BETA")
        assert [r for r in range(3) if not table.table.isRowHidden(r)] == [1]
        table.search_edit.setText("missing")
        assert all(table.table.isRowHidden(r) for r in range(3))
        table.search_edit.setText("mm")
        assert [r for r in range(3) if not table.table.isRowHidden(r)] == [2]
    finally:
        _close_table(table, qapp)


def test_type_filter_uses_extension_categories(qapp, tmp_path):
    table, _paths = _make_table(qapp, tmp_path, ("cover.png", "clip.mp4", "loop.gif", "scene.pkg"))
    try:
        table.type_filter.setCurrentText("图片")
        assert [r for r in range(4) if not table.table.isRowHidden(r)] == [0]
        table.type_filter.setCurrentText("视频")
        assert [r for r in range(4) if not table.table.isRowHidden(r)] == [1]
        table.type_filter.setCurrentText("GIF")
        assert [r for r in range(4) if not table.table.isRowHidden(r)] == [2]
        table.type_filter.setCurrentText("壁纸包")
        assert [r for r in range(4) if not table.table.isRowHidden(r)] == [3]
        table.type_filter.setCurrentText("全部类型")
        assert not any(table.table.isRowHidden(r) for r in range(4))
    finally:
        _close_table(table, qapp)


def test_status_filter_matches_current_status_text(qapp, tmp_path):
    table, paths = _make_table(qapp, tmp_path, ("one.png", "two.png"))
    try:
        table.set_status_for_path(paths[0], "done")
        table.status_filter.setCurrentText("完成")
        assert not table.table.isRowHidden(0)
        assert table.table.isRowHidden(1)
        table.set_status_for_path(paths[1], "failed", "编码失败")
        table.status_filter.setCurrentText("失败")
        assert table.table.isRowHidden(0)
        assert not table.table.isRowHidden(1)
        table.set_status_for_path(paths[1], "cancelled", "用户取消")
        table.status_filter.setCurrentText("已取消")
        assert not table.table.isRowHidden(1)
    finally:
        _close_table(table, qapp)


def test_filtering_does_not_change_selection_contracts(qapp, tmp_path):
    table, paths = _make_table(qapp, tmp_path, ("keep.png", "hidden.mp4", "other.pkg"))
    try:
        table.table.selectRow(1)
        table.search_edit.setText("keep")
        assert table.selected_or_all() == [paths[1]]
        table.table.clearSelection()
        assert table.selected_or_all() == paths
        assert table.all_paths() == paths
        table.select_all()
        table.search_edit.setText("other")
        assert table.selected_or_all() == paths
    finally:
        _close_table(table, qapp)


def test_add_and_status_update_work_for_filtered_rows(qapp, tmp_path):
    from gui.widgets.file_table import FileTable

    table = FileTable({".png", ".mp4"})
    hidden = tmp_path / "hidden.png"
    visible = tmp_path / "visible.mp4"
    hidden.write_bytes(b"test")
    visible.write_bytes(b"test")
    try:
        table.search_edit.setText("visible")
        table.add_paths([hidden])
        assert table.table.isRowHidden(0)
        table.add_paths([visible])
        assert not table.table.isRowHidden(1)
        assert table.all_paths() == [hidden, visible]
        table.set_status_for_path(hidden, "done")
        assert table.table.item(0, 3).text() == "完成"
        table.status_filter.setCurrentText("完成")
        assert table.table.isRowHidden(0)
    finally:
        _close_table(table, qapp)


def test_preview_button_is_enabled_only_for_image_selection(qapp, png_64, tmp_path):
    from gui.widgets.file_table import FileTable

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"test")
    table = FileTable({".png", ".mp4"})
    table.add_paths([png_64, video])
    try:
        assert not table.preview_btn.isEnabled()
        table.table.selectRow(0)
        assert table.preview_btn.isEnabled()
        table.table.selectRow(1)
        assert not table.preview_btn.isEnabled()
    finally:
        _close_table(table, qapp)


def test_thumbnail_loading_is_lazy_and_visible_row_scoped(qapp, tmp_path):
    from gui.widgets.file_table import FileTable

    table = FileTable({".png"})
    paths = []
    for index in range(20):
        path = tmp_path / f"thumb{index}.png"
        path.write_bytes(b"test")
        paths.append(path)
    try:
        table.add_paths(paths)
        assert table._thumbnail_cache == {}
        table.resize(420, 150)
        table.show()
        qapp.processEvents()
        table._load_visible_thumbnails()
        visible = [row for row in range(len(paths)) if not table.table.isRowHidden(row)]
        assert 0 < len(table._thumbnail_cache) <= len(visible)
    finally:
        _close_table(table, qapp)


def test_preview_opens_resizable_dialog_with_name_and_size(qapp, png_64):
    from gui.widgets.file_table import FileTable

    table = FileTable({".png"})
    table.add_paths([png_64])
    table.table.selectRow(0)
    dialog = None
    try:
        table.preview_selected()
        qapp.processEvents()
        dialog = table._preview_dialog
        assert dialog is not None
        assert dialog.isWindow()
        assert dialog.windowTitle() == "图片预览"
        assert dialog.image_path == png_64
        assert png_64.name in dialog.info.text()
        assert "KB" in dialog.info.text()
        assert dialog.preview_kind == "static"
        assert dialog.movie is None
    finally:
        if dialog is not None:
            dialog.close()
        _close_table(table, qapp)


def test_gif_preview_uses_animated_movie(qapp, gif_2f):
    from PySide6.QtGui import QMovie

    from gui.widgets.file_table import ImagePreviewDialog

    dialog = ImagePreviewDialog(gif_2f)
    try:
        assert dialog.preview_kind == "movie"
        assert dialog.movie is not None
        assert dialog.movie.isValid()
        dialog.resize(720, 520)
        dialog.show()
        for _ in range(20):
            qapp.processEvents()
        pixmap = dialog.image.pixmap()
        if pixmap is None or pixmap.isNull():
            assert dialog.movie.jumpToFrame(0)
            for _ in range(5):
                qapp.processEvents()
            pixmap = dialog.image.pixmap()
        assert dialog.movie.state() == QMovie.Running
        assert gif_2f.name in dialog.info.text()
        assert pixmap is not None and not pixmap.isNull()
        assert dialog.image.width() > 0
    finally:
        dialog.close()
        qapp.processEvents()


def test_hidden_selection_still_opens_output(qapp, tmp_path):
    from gui.widgets.file_table import FileTable

    source = tmp_path / "hidden.png"
    output = tmp_path / "converted" / "hidden.png"
    source.write_bytes(b"test")
    output.parent.mkdir()
    output.write_bytes(b"done")
    table = FileTable({".png"})
    table.add_paths([source])
    table.set_output_map({str(source): output})
    emitted = []
    table.open_output_requested.connect(emitted.append)
    table.table.selectRow(0)
    table.search_edit.setText("not-present")
    table._open_output()
    try:
        assert emitted == [output]
    finally:
        _close_table(table, qapp)


def test_cancel_shortcut_respects_running_and_modal_state(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    window = _window(qapp, tmp_path, monkeypatch)
    page = window.image_page
    page.cancel_btn.setEnabled(True)
    calls = []
    page.cancel_btn.clicked.connect(lambda: calls.append(True))
    try:
        monkeypatch.setattr(window, "_batch_is_running", lambda: True)
        window._sync_shortcut_state()
        assert window.cancel_shortcut.isEnabled()
        dialog = QMessageBox(window)
        dialog.setWindowTitle("测试对话框")
        dialog.setText("测试")
        dialog.setModal(True)
        dialog.show()
        qapp.processEvents()
        qapp.processEvents()
        assert not window.cancel_shortcut.isEnabled()
        dialog.close()
        qapp.processEvents()
        qapp.processEvents()
        window._sync_shortcut_state()
        assert window.cancel_shortcut.isEnabled()
        window._shortcut_cancel()
        assert calls == [True]
        monkeypatch.setattr(window, "_batch_is_running", lambda: False)
        window._sync_shortcut_state()
        window._shortcut_cancel()
        assert calls == [True]
    finally:
        window.close()
        window.deleteLater()
        qapp.processEvents()


def test_window_ctrl_a_selects_all_real_rows_through_shortcut(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    window = _window(qapp, tmp_path, monkeypatch)
    paths = []
    for name in ("one.png", "two.mp4", "three.pkg"):
        path = tmp_path / name
        path.write_bytes(b"test")
        paths.append(path)
    try:
        table = window.image_page.table
        table.set_accept_exts({".png", ".mp4", ".pkg"})
        table.add_paths(paths)
        table.search_edit.setText("one")
        window.show()
        table.table.setFocus()
        qapp.processEvents()
        QTest.keyClick(window, Qt.Key_A, Qt.ControlModifier)
        qapp.processEvents()
        assert table.selected_or_all() == paths
    finally:
        window.close()
        window.deleteLater()
        qapp.processEvents()


def test_main_window_registers_expected_shortcuts(qapp, tmp_path, monkeypatch):
    from PySide6.QtGui import QShortcut

    window = _window(qapp, tmp_path, monkeypatch)
    try:
        expected = {
            "add_files": "Ctrl+O",
            "add_folder": "Ctrl+Shift+O",
            "start": "Ctrl+Enter",
            "cancel": "Esc",
            "select_all": "Ctrl+A",
        }
        for name, key in expected.items():
            shortcut = window.shortcuts[name]
            assert isinstance(shortcut, QShortcut)
            assert shortcut.key().toString() == key
        assert window.cancel_shortcut.isEnabled() is False
    finally:
        window.close()
        window.deleteLater()
        qapp.processEvents()
