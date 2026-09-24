from __future__ import annotations

import json
from pathlib import Path

_DEFAULTS = {
    "output_mode": "beside",
    "unified_dir": "",
    "default_quality": 90,
    "default_gif_fps": 15,
    "auto_check_update": True,
    "window_geometry": "",
    "active_page": 0,
    "last_image_format": "JPG",
    "last_video_format": "MP4",
    "last_dir": "",
}


def settings_dir() -> Path:
    base = Path.home() / "AppData" / "Roaming" / "WallpaperConverter"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _settings_path() -> Path:
    return settings_dir() / "settings.json"


def load_settings() -> dict:
    p = _settings_path()
    data = dict(_DEFAULTS)
    if p.is_file():
        try:
            loaded = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update({k: loaded[k] for k in _DEFAULTS if k in loaded})
        except (json.JSONDecodeError, OSError):
            pass
    return data


def save_settings(settings: dict) -> None:
    data = load_settings()
    data.update({k: settings[k] for k in _DEFAULTS if k in settings})
    _settings_path().write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
