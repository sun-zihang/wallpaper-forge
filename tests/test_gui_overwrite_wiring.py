import json
from pathlib import Path
from types import SimpleNamespace

import pytest


_PAGE_KINDS = (
    "image",
    "gif",
    "gif_split",
    "video",
    "video_frames",
    "unpack",
    "rewatermark",
)


@pytest.fixture
def base_page(qapp):
    from gui.pages.base import BasePage

    page = BasePage()
    yield page
    page.close()
    page.deleteLater()
    qapp.processEvents()


def _build_page_case(kind: str, qapp, tmp_path: Path, monkeypatch):
    if kind == "image":
        from gui.pages import image_page as module

        page = module.ImagePage()
        sources = [tmp_path / "image.png"]
        resolver_name = "resolve_outputs"
    elif kind == "gif":
        from gui.pages import gif_page as module

        page = module.GifPage()
        page.mode.setCurrentIndex(1)
        sources = [tmp_path / "first.png", tmp_path / "second.png"]
        resolver_name = "resolve_outputs"
    elif kind == "gif_split":
        from gui.pages import gif_page as module

        page = module.GifPage()
        page.mode.setCurrentIndex(0)  # split
        sources = [tmp_path / "anim.gif"]
        resolver_name = "resolve_out_dir"
    elif kind == "video":
        from gui.pages import video_page as module

        page = module.VideoPage()
        sources = [tmp_path / "clip.mp4"]
        resolver_name = "resolve_outputs"
        monkeypatch.setattr(module, "ffmpeg_available", lambda: True)
    elif kind == "video_frames":
        from gui.pages import video_page as module

        page = module.VideoPage()
        page.mode.setCurrentIndex(2)  # frames
        sources = [tmp_path / "clip.mp4"]
        resolver_name = "resolve_out_dir"
        monkeypatch.setattr(module, "ffmpeg_available", lambda: True)
    elif kind == "unpack":
        from gui.pages import unpack_page as module

        page = module.UnpackPage()
        sources = [tmp_path / "scene.pkg"]
        resolver_name = "_out_dir_for"
    elif kind == "rewatermark":
        from gui.pages import rewatermark_page as module

        page = module.RewatermarkPage()
        sources = [tmp_path / "image.png"]
        resolver_name = "_clean_out"
    else:
        raise ValueError(f"unknown page kind: {kind}")

    for source in sources:
        source.write_bytes(b"test")
    page.table.add_paths(sources)
    if kind == "rewatermark":
        page._boxes[sources[0]] = [(0, 0, 1, 1)]

    resolver_calls = []
    resolver = getattr(module, resolver_name)

    def tracked_resolver(*args, **kwargs):
        resolver_calls.append({"args": args, "kwargs": kwargs.copy()})
        return resolver(*args, **kwargs)

    submitted = []
    monkeypatch.setattr(module, resolver_name, tracked_resolver)
    monkeypatch.setattr(page, "_submit", lambda batch: submitted.append(list(batch)))
    qapp.processEvents()
    return SimpleNamespace(
        page=page,
        resolver_name=resolver_name,
        resolver_calls=resolver_calls,
        submitted=submitted,
    )


@pytest.fixture
def page_case(qapp, tmp_path, monkeypatch):
    pages = []

    def build(kind: str):
        case = _build_page_case(kind, qapp, tmp_path, monkeypatch)
        pages.append(case.page)
        return case

    yield build
    for page in pages:
        page.close()
        page.deleteLater()
    qapp.processEvents()


def test_overwrite_check_exists_and_defaults_unchecked(base_page, qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QCheckBox

    assert isinstance(base_page.overwrite_check, QCheckBox)
    assert base_page.overwrite_check.isChecked() is False
    assert base_page.overwrite_check.checkState() == Qt.Unchecked


def test_overwrite_check_is_not_loaded_or_applied_from_settings(
    base_page, tmp_path, monkeypatch
):
    from gui import settings_store

    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "output_mode": "unified",
                "unified_dir": str(tmp_path / "unified"),
                "overwrite": True,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    settings = settings_store.load_settings()

    assert "overwrite" not in settings
    base_page.apply_settings(settings)
    assert base_page.overwrite_check.isChecked() is False
    base_page.overwrite_check.setChecked(True)
    base_page.apply_settings(settings)
    assert base_page.overwrite_check.isChecked() is True
    base_page.apply_settings({"overwrite": False})
    assert base_page.overwrite_check.isChecked() is True


def test_confirm_overwrite_skips_dialog_when_unchecked(base_page, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    calls = []

    def question(*args):
        calls.append(args)
        return QMessageBox.Yes

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    source = tmp_path / "image.png"
    source.write_bytes(b"test")
    base_page.overwrite_check.setChecked(False)

    assert base_page._confirm_overwrite([source], [source]) is True
    assert calls == []


def test_confirm_overwrite_skips_dialog_without_source_collision(
    base_page, monkeypatch, tmp_path
):
    from PySide6.QtWidgets import QMessageBox

    calls = []

    def question(*args):
        calls.append(args)
        return QMessageBox.Yes

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    source = tmp_path / "image.png"
    output = tmp_path / "converted" / "image.png"
    source.write_bytes(b"test")
    base_page.overwrite_check.setChecked(True)

    assert base_page._confirm_overwrite([source], [output]) is True
    assert calls == []


@pytest.mark.parametrize(
    ("button_name", "expected"),
    [("yes", True), ("no", False)],
)
def test_confirm_overwrite_uses_safe_dialog_for_source_collision(
    base_page, monkeypatch, tmp_path, button_name, expected
):
    from PySide6.QtWidgets import QMessageBox

    dialog_result = QMessageBox.Yes if button_name == "yes" else QMessageBox.No
    calls = []

    def question(parent, title, body, buttons, default_button):
        calls.append((parent, title, body, buttons, default_button))
        return dialog_result

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    sources = [tmp_path / "first.png", tmp_path / "second.png"]
    for source in sources:
        source.write_bytes(b"test")
    base_page.overwrite_check.setChecked(True)

    result = base_page._confirm_overwrite(sources, list(sources))

    assert result is expected
    assert len(calls) == 1
    parent, title, body, buttons, default_button = calls[0]
    assert parent is base_page
    assert title == "确认覆盖"
    assert "2 个源文件" in body
    assert "此操作不可恢复" in body
    assert buttons == QMessageBox.Yes | QMessageBox.No
    assert default_button == QMessageBox.No


@pytest.mark.parametrize("kind", _PAGE_KINDS)
@pytest.mark.parametrize("checked", [False, True], ids=["unchecked", "checked"])
def test_start_batch_passes_overwrite_to_page_resolver(
    kind, checked, page_case
):
    case = page_case(kind)
    case.page.overwrite_check.setChecked(checked)

    case.page.start_batch()

    assert len(case.resolver_calls) == 1
    assert case.resolver_calls[0]["kwargs"].get("overwrite", False) is checked
    assert len(case.submitted) == 1
    assert len(case.submitted[0]) == 1
    if kind == "gif":
        assert len(case.submitted[0][0].sources) == 2


@pytest.mark.parametrize("kind", _PAGE_KINDS)
def test_start_batch_does_not_submit_after_overwrite_cancel(
    kind, page_case, monkeypatch
):
    case = page_case(kind)
    case.page.overwrite_check.setChecked(True)
    confirmations = []

    def reject(sources, outputs):
        confirmations.append((list(sources), list(outputs)))
        return False

    monkeypatch.setattr(case.page, "_confirm_overwrite", reject)

    case.page.start_batch()

    assert len(case.resolver_calls) == 1
    assert case.resolver_calls[0]["kwargs"].get("overwrite", False) is True
    assert len(confirmations) == 1
    assert case.submitted == []
