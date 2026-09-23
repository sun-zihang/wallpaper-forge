from gui.settings_store import _DEFAULTS, load_settings


def test_defaults_include_quality_and_fps():
    assert _DEFAULTS["default_quality"] == 90
    assert _DEFAULTS["default_gif_fps"] == 15


def test_load_settings_returns_defaults():
    s = load_settings()
    assert isinstance(s.get("default_quality"), int)
    assert isinstance(s.get("default_gif_fps"), int)
