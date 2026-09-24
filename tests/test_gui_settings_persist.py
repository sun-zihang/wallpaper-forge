import json


def test_image_format_round_trips_through_settings(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.pages import base as base_mod
    from gui.pages import image_page as module

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    saves = []
    real_save = base_mod.save_settings
    monkeypatch.setattr(
        base_mod,
        "save_settings",
        lambda patch: (saves.append(dict(patch)), real_save(patch))[1],
    )

    page = module.ImagePage()
    assert saves == []

    page.fmt.setCurrentText("WebP")
    assert settings_store.load_settings()["last_image_format"] == "WebP"
    assert saves == [{"last_image_format": "WebP"}]

    page2 = module.ImagePage()
    page2.apply_settings(settings_store.load_settings())
    assert page2.fmt.currentText() == "WebP"
    assert len(saves) == 1

    page.close()
    page2.close()
    page.deleteLater()
    page2.deleteLater()
    qapp.processEvents()


def test_mode_and_dir_write_through_but_loading_does_not_save(
    qapp, tmp_path, monkeypatch
):
    from gui.pages import base as base_mod
    from gui.pages.base import BasePage

    calls = []
    monkeypatch.setattr(base_mod, "save_settings", lambda patch: calls.append(dict(patch)))

    page = BasePage()
    page.apply_settings({"output_mode": "unified", "unified_dir": str(tmp_path)})
    assert calls == []
    assert page.output_mode.currentIndex() == 1

    page.output_mode.setCurrentIndex(0)
    assert calls == [{"output_mode": "beside"}]
    assert page._settings["output_mode"] == "beside"

    picked = tmp_path / "picked"
    monkeypatch.setattr(
        base_mod.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *a, **k: str(picked)),
    )
    page._pick_out()
    assert calls[-1] == {"unified_dir": str(picked), "last_dir": str(picked)}
    assert page.unified_dir == picked

    count_after_changes = len(calls)
    page.apply_settings({"output_mode": "unified"})
    assert page.output_mode.currentIndex() == 1
    assert len(calls) == count_after_changes

    page.close()
    page.deleteLater()
    qapp.processEvents()


def test_main_window_restores_page_and_saves_geometry(qapp, tmp_path, monkeypatch):
    from gui import settings_store
    from gui.main_window import MainWindow

    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"active_page": 2, "auto_check_update": False}),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    win = MainWindow("0.0.0-test")
    assert win.nav.currentRow() == 2
    assert win.stack.currentIndex() == 2

    win.nav.setCurrentRow(4)
    win.close()
    saved = settings_store.load_settings()
    assert saved["active_page"] == 4
    assert saved["window_geometry"]

    win.deleteLater()
    qapp.processEvents()
