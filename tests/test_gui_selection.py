def test_select_all_inverse_and_counts(qapp, tmp_path):
    from gui.widgets.file_table import FileTable

    table = FileTable()
    assert table.hint.text() == "拖拽文件/文件夹到此处，或使用下方按钮添加"

    files = []
    for i in range(3):
        p = tmp_path / f"f{i}.png"
        p.write_bytes(b"x")
        files.append(p)
    table.add_paths(files)

    assert table.hint.text() == "已选中 0/3（未选中则处理全部）"
    assert table.selected_or_all() == files

    table.select_all()
    assert {i.row() for i in table.table.selectedIndexes()} == {0, 1, 2}
    assert table.hint.text() == "已选中 3/3（未选中则处理全部）"

    table.invert_selection()
    assert {i.row() for i in table.table.selectedIndexes()} == set()
    assert table.hint.text() == "已选中 0/3（未选中则处理全部）"
    assert table.selected_or_all() == files

    table.invert_selection()
    assert {i.row() for i in table.table.selectedIndexes()} == {0, 1, 2}
    assert table.hint.text() == "已选中 3/3（未选中则处理全部）"

    table.table.clearSelection()
    table.table.selectRow(1)
    assert table.hint.text() == "已选中 1/3（未选中则处理全部）"
    assert table.selected_or_all() == [files[1]]

    table.clear()
    assert table.hint.text() == "拖拽文件/文件夹到此处，或使用下方按钮添加"
    table.deleteLater()
    qapp.processEvents()


def test_crop_reports_first_file_for_multi_selection(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QLabel, QMainWindow

    from gui.pages import image_page as module

    page = module.ImagePage()
    host = QMainWindow()
    host.status_label = QLabel("")
    host.setCentralWidget(page)

    files = []
    for name in ("a.png", "b.png"):
        p = tmp_path / name
        p.write_bytes(b"x")
        files.append(p)
    page.table.add_paths(files)
    page.table.table.selectAll()

    boxes = []
    monkeypatch.setattr(
        module.CropDialog,
        "get_box",
        staticmethod(lambda parent, path: boxes.append(path) or None),
    )

    page._crop()

    assert boxes == [files[0]]
    assert files[0].name in host.status_label.text()
    assert "第一个" in host.status_label.text()

    host.close()
    host.deleteLater()
    qapp.processEvents()


def test_watermark_reports_count_for_multi_selection(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QLabel, QMainWindow

    from gui.pages import image_page as module

    page = module.ImagePage()
    host = QMainWindow()
    host.status_label = QLabel("")
    host.setCentralWidget(page)

    files = []
    for name in ("a.png", "b.png"):
        p = tmp_path / name
        p.write_bytes(b"x")
        files.append(p)
    page.table.add_paths(files)
    page.table.table.selectAll()

    monkeypatch.setattr(module.WatermarkDialog, "get_params", staticmethod(lambda parent: None))

    page._watermark()

    assert "2 个文件" in host.status_label.text()

    host.close()
    host.deleteLater()
    qapp.processEvents()
