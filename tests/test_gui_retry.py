from pathlib import Path


def _setup_sync_submit(page, monkeypatch):
    def sync_submit(batch):
        page.thread._batch = list(batch)
        page.thread.runner.run_batch(page.thread._batch)
        page.thread._batch = []

    monkeypatch.setattr(page.thread, "submit", sync_submit)


def _patch_dialog(monkeypatch, offered):
    from PySide6.QtWidgets import QMessageBox

    def fake_exec(self):
        names = [b.text() for b in self.buttons()]
        offered.append(names)
        retry = next((b for b in self.buttons() if b.text() == "重试失败项"), None)
        if retry is not None:
            retry.click()
        else:
            self.button(QMessageBox.Ok).click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)


def test_retry_failed_resubmits_only_failed_subset(qapp, tmp_path, monkeypatch):
    import gui.workers as workers
    from gui.pages.gif_page import GifPage

    page = GifPage()
    good = tmp_path / "good.gif"
    bad = tmp_path / "bad.gif"
    good.write_bytes(b"GIF89a")
    bad.write_bytes(b"GIF89a")
    page.table.add_paths([good, bad])

    processed = []
    state = {"bad_failed": False}

    def fake_execute(task, progress_cb=None):
        name = task.sources[0].name
        processed.append(name)
        if name == "bad.gif" and not state["bad_failed"]:
            state["bad_failed"] = True
            raise RuntimeError("模拟失败")
        out_dir = Path(task.params["out_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        frame = out_dir / "f.png"
        frame.write_bytes(b"png")
        task.outputs = [frame]

    monkeypatch.setattr(workers, "execute_task", fake_execute)
    _setup_sync_submit(page, monkeypatch)
    offered = []
    _patch_dialog(monkeypatch, offered)

    page.start_batch()

    assert page._last_ok == 1
    assert page._last_failed == 0
    assert page._failed_tasks == []
    assert processed.count("good.gif") == 1
    assert processed.count("bad.gif") == 2
    assert len(offered) == 2
    assert "重试失败项" in offered[0]
    assert "打开输出文件夹" in offered[0]
    assert all("重试失败项" not in names for names in offered[1:])
    assert page.start_btn.isEnabled()
    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_batch_done_offers_retry_only_with_failed_tasks(qapp):
    from core.tasks import Task, TaskKind
    from gui.pages.base import BasePage

    page = BasePage()
    box, _open_btn, retry_btn = page._build_batch_box(0, 0)
    assert retry_btn is None
    box.done(0)

    task = Task(sources=[Path("x.png")], kind=TaskKind.IMAGE_CONVERT)
    page._failed_tasks = [task]
    box, _open_btn, retry_btn = page._build_batch_box(1, 1)
    assert retry_btn is not None
    assert retry_btn.text() == "重试失败项"
    box.done(0)

    page._failed_tasks = []
    box, _open_btn, retry_btn = page._build_batch_box(1, 1)
    assert retry_btn is None
    box.done(0)
    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_retry_failed_respects_overwrite_gate(qapp, tmp_path, monkeypatch):
    from core.tasks import OutputMode, Task, TaskKind
    from gui.pages.image_page import ImagePage

    page = ImagePage()
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    page.table.add_paths([src])
    page.overwrite_check.setChecked(True)
    task = Task(
        sources=[src],
        kind=TaskKind.IMAGE_CONVERT,
        output_mode=OutputMode.BESIDE,
        outputs=[tmp_path / "converted" / "a.jpg"],
    )

    confirms = []
    submits = []
    monkeypatch.setattr(
        page,
        "_confirm_overwrite",
        lambda s, o: confirms.append((list(s), list(o))) or False,
    )
    monkeypatch.setattr(page, "_submit", lambda b: submits.append(list(b)))

    page._failed_tasks = [task]
    page._retry_failed()

    assert len(confirms) == 1
    assert confirms[0][0] == [src]
    assert submits == []
    assert page._failed_tasks == []

    page._failed_tasks = [task]
    monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: True)
    page._retry_failed()

    assert len(submits) == 1
    assert len(submits[0]) == 1
    assert list(submits[0][0].sources) == [src]
    assert page._failed_tasks == []
    assert page._retry_paths is None
    page.close()
    page.deleteLater()
    qapp.processEvents()
