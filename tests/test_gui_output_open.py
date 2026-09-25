from pathlib import Path

import pytest


@pytest.fixture
def base_page(qapp):
    from gui.pages.base import BasePage

    page = BasePage()
    yield page
    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_completion_dialog_open_folder_uses_real_output(base_page, tmp_path, monkeypatch):
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QMessageBox

    out_dir = tmp_path / "unified"
    out_dir.mkdir()
    out = out_dir / "a.jpg"
    out.write_bytes(b"x")
    base_page.last_outputs = [out]

    opened = []
    monkeypatch.setattr(
        QDesktopServices,
        "openUrl",
        staticmethod(lambda url: opened.append(url.toLocalFile()) or True),
    )

    def fake_exec(self):
        btn = next(b for b in self.buttons() if b.text() == "打开输出文件夹")
        assert btn.isEnabled()
        btn.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    base_page._on_batch_done(1, 0)

    assert [Path(p) for p in opened] == [out_dir]


def test_completion_dialog_open_disabled_without_outputs(base_page):
    base_page.last_outputs = []
    box, open_btn, retry_btn = base_page._build_batch_box(1, 0)
    assert open_btn.text() == "打开输出文件夹"
    assert not open_btn.isEnabled()
    assert retry_btn is None
    box.done(0)

    base_page.last_outputs = [Path("x")]
    box2, open_btn2, _ = base_page._build_batch_box(1, 0)
    assert open_btn2.isEnabled()
    box2.done(0)


def test_double_click_reveals_real_output_after_batch(base_page, tmp_path):
    from core.tasks import OutputMode, Task, TaskKind

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    src = src_dir / "a.png"
    src.write_bytes(b"x")
    unified = tmp_path / "unified"
    unified.mkdir()
    out = unified / "a.jpg"
    out.write_bytes(b"y")

    base_page.table.add_paths([src])
    task = Task(
        sources=[src],
        kind=TaskKind.IMAGE_CONVERT,
        output_mode=OutputMode.UNIFIED,
        unified_dir=unified,
        outputs=[out],
        status="done",
    )
    base_page._on_task(task)

    got = []
    base_page.table.open_output_requested.connect(got.append)
    base_page.table.table.selectRow(0)
    base_page.table._open_output()

    assert got == [out]
    assert got[0] != src_dir
    assert got[0] != src_dir / "converted"


def test_double_click_falls_back_to_guessed_folder(base_page, tmp_path):
    src_dir = tmp_path / "work"
    src_dir.mkdir()
    src = src_dir / "b.png"
    src.write_bytes(b"x")
    base_page.table.add_paths([src])

    got = []
    base_page.table.open_output_requested.connect(got.append)
    base_page.table.table.selectRow(0)
    base_page.table._open_output()

    assert got == [src_dir]


def test_open_path_selects_file_via_explorer(base_page, tmp_path, monkeypatch):
    import types

    from gui.pages import base as base_mod

    out = tmp_path / "a.jpg"
    out.write_bytes(b"x")
    calls = []
    monkeypatch.setattr(
        base_mod, "subprocess", types.SimpleNamespace(Popen=lambda args: calls.append(args))
    )

    base_page._open_path(out)

    assert calls == [["explorer.exe", "/select,", str(out)]]


def test_open_path_opens_folder_via_qdesktopservices(base_page, tmp_path, monkeypatch):
    from PySide6.QtGui import QDesktopServices

    folder = tmp_path / "unified"
    folder.mkdir()
    opened = []
    monkeypatch.setattr(
        QDesktopServices,
        "openUrl",
        staticmethod(lambda url: opened.append(url.toLocalFile()) or True),
    )

    base_page._open_path(folder)

    assert [Path(p) for p in opened] == [folder]
