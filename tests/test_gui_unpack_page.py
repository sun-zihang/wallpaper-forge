"""UnpackPage start_batch extension filter, kind mapping, and guards."""

from __future__ import annotations

from pathlib import Path


def _page(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.pages.unpack_page import UnpackPage

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)
    return UnpackPage()


def test_accept_exts_and_start_label(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        assert set(page.table.accept_exts) == {".pkg", ".tex", ".mpkg"}
        assert page.start_btn.text() == "开始解包"
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_start_batch_empty_message(qapp, tmp_path, monkeypatch):
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
        assert msgs and ".pkg / .tex / .mpkg" in msgs[0]
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_start_batch_maps_ext_to_kind_and_builds_dirs(qapp, tmp_path, monkeypatch):
    from core.tasks import TaskKind

    page = _page(qapp, tmp_path, monkeypatch)
    try:
        pkg = tmp_path / "a.pkg"
        tex = tmp_path / "b.tex"
        mpkg = tmp_path / "c.mpkg"
        junk = tmp_path / "d.txt"
        for p in (pkg, tex, mpkg, junk):
            p.write_bytes(b"x")

        page.table.add_paths([pkg, tex, mpkg, junk])
        submitted = []
        monkeypatch.setattr(page, "_submit", lambda b: submitted.append(b))
        monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: True)
        page.start_batch()
        assert len(submitted) == 1
        batch = submitted[0]
        assert len(batch) == 3  # junk filtered
        kinds = {t.sources[0].suffix: t.kind for t in batch}
        assert kinds[".pkg"] is TaskKind.UNPACK_PKG
        assert kinds[".tex"] is TaskKind.UNPACK_TEX
        assert kinds[".mpkg"] is TaskKind.UNPACK_MPKG
        dirs = [t.params["out_dir"] for t in batch]
        assert len(set(dirs)) == 3
        assert all(d.parent.exists() for d in dirs)
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_start_batch_declined_overwrite_no_submit(qapp, tmp_path, monkeypatch):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        pkg = tmp_path / "a.pkg"
        pkg.write_bytes(b"x")
        page.table.add_paths([pkg])
        submitted = []
        monkeypatch.setattr(page, "_submit", lambda b: submitted.append(b))
        monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: False)
        page.start_batch()
        assert submitted == []
    finally:
        page.deleteLater()
        qapp.processEvents()


def test_start_batch_creates_unique_out_dirs_when_not_overwrite(
    qapp, tmp_path, monkeypatch
):
    page = _page(qapp, tmp_path, monkeypatch)
    try:
        # two same-stem different-ext would collide differently; use taken via same name impossible
        # use two files that resolve_out_dir would number: pre-create first out dir non-empty
        a = tmp_path / "a.pkg"
        a.write_bytes(b"x")
        page.table.add_paths([a])
        # first resolve produces converted/a; pre-create it non-empty so second run numbers
        conv = tmp_path / "converted"
        # start once with overwrite to create base dir contents via resolve only (no write)
        submitted = []
        monkeypatch.setattr(page, "_submit", lambda b: submitted.append(b))
        monkeypatch.setattr(page, "_confirm_overwrite", lambda s, o: True)
        page.overwrite_check.setChecked(False)
        page.start_batch()
        out0 = submitted[0][0].params["out_dir"]
        out0.mkdir(parents=True, exist_ok=True)
        (out0 / "x.bin").write_bytes(b"1")
        page.overwrite_check.setChecked(False)
        page.start_batch()
        out1 = submitted[1][0].params["out_dir"]
        assert out1 != out0
    finally:
        page.deleteLater()
        qapp.processEvents()
