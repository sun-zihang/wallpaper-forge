import json

from gui.settings_store import _DEFAULTS, load_settings, save_settings


def test_defaults_include_quality_and_fps():
    assert _DEFAULTS["default_quality"] == 90
    assert _DEFAULTS["default_gif_fps"] == 15


def test_defaults_include_persistence_keys():
    assert _DEFAULTS["window_geometry"] == ""
    assert _DEFAULTS["active_page"] == 0
    assert _DEFAULTS["last_image_format"] == "JPG"
    assert _DEFAULTS["last_video_format"] == "MP4"
    assert _DEFAULTS["last_dir"] == ""


def test_load_settings_returns_defaults():
    s = load_settings()
    assert isinstance(s.get("default_quality"), int)
    assert isinstance(s.get("default_gif_fps"), int)
    assert s.get("last_image_format") == "JPG"
    assert s.get("active_page") == 0
    assert s.get("window_geometry") == ""


def test_old_schema_file_loads_with_new_defaults(tmp_path, monkeypatch):
    from gui import settings_store

    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"output_mode": "unified", "default_quality": 80}),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    s = load_settings()

    assert s["output_mode"] == "unified"
    assert s["default_quality"] == 80
    assert s["last_image_format"] == "JPG"
    assert s["last_video_format"] == "MP4"
    assert s["active_page"] == 0
    assert s["window_geometry"] == ""
    assert s["last_dir"] == ""


def test_save_load_round_trip_and_partial_save_preserves(tmp_path, monkeypatch):
    from gui import settings_store

    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    save_settings(
        {
            "last_image_format": "WebP",
            "active_page": 3,
            "window_geometry": "abc",
            "last_dir": str(tmp_path),
        }
    )
    s = load_settings()
    assert s["last_image_format"] == "WebP"
    assert s["active_page"] == 3
    assert s["window_geometry"] == "abc"
    assert s["last_dir"] == str(tmp_path)

    save_settings({"output_mode": "unified"})
    s2 = load_settings()
    assert s2["output_mode"] == "unified"
    assert s2["last_image_format"] == "WebP"
    assert s2["active_page"] == 3
    assert s2["window_geometry"] == "abc"


def test_save_filters_unknown_keys(tmp_path, monkeypatch):
    from gui import settings_store

    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    save_settings({"overwrite": True, "output_mode": "beside"})

    s = load_settings()
    assert "overwrite" not in s
    assert s["output_mode"] == "beside"


def test_corrupt_settings_json_falls_back_to_defaults(tmp_path, monkeypatch):
    from gui import settings_store

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    s = load_settings()
    assert s["default_quality"] == 90
    assert s["output_mode"] == "beside"


def test_non_dict_settings_json_falls_back_to_defaults(tmp_path, monkeypatch):
    from gui import settings_store

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("[1,2,3]", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: settings_path)

    s = load_settings()
    assert s["last_image_format"] == "JPG"


def test_auto_check_update_default_true():
    assert _DEFAULTS["auto_check_update"] is True
    assert _DEFAULTS["unified_dir"] == ""
