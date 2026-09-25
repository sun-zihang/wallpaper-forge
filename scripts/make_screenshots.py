"""Render README screenshots.

The offscreen platform cannot enumerate system fonts (Chinese renders as
tofu boxes), so the real Windows QPA is used; the window is grabbed right
after show() before it can take focus.

Usage:  python scripts/make_screenshots.py
Outputs: docs/assets/desktop-main.png, docs/assets/desktop-settings.png
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SAMPLES = [
    ("sakura-dawn-4k.png", (255, 228, 235)),
    ("neon-city-night.jpg", (24, 24, 64)),
    ("mountain-fog.webp", (200, 210, 215)),
    ("ocean-wave-loop.gif", (30, 90, 160)),
]


def main() -> None:
    from PIL import Image

    from core.version import __version__
    from gui import settings_store
    from gui.main_window import MainWindow

    tmp = Path(tempfile.mkdtemp(prefix="shots-"))
    settings_path = tmp / "settings.json"
    settings_path.write_text(json.dumps({"auto_check_update": False}), encoding="utf-8")
    settings_store._settings_path = lambda: settings_path

    # stable path so repeated runs produce identical-looking file paths
    sample_dir = Path(tempfile.gettempdir()) / "wallpaper-forge-samples"
    sample_dir.mkdir(parents=True, exist_ok=True)
    for old in sample_dir.iterdir():
        old.unlink(missing_ok=True)
    for name, color in SAMPLES:
        img = Image.new("RGB", (1920, 1080), color)
        ext = Path(name).suffix.lower()
        if ext == ".gif":
            img.save(sample_dir / name, save_all=True, duration=100, loop=0)
        else:
            img.save(sample_dir / name)

    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    families = set(QFontDatabase().families())
    for candidate in ("Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "Noto Sans CJK SC"):
        if candidate in families:
            app.setFont(QFont(candidate, 10))
            break
    win = MainWindow(__version__)
    win.resize(1280, 820)
    win.show()
    app.processEvents()

    win.image_page.table.add_paths([sample_dir / n for n, _ in SAMPLES])
    app.processEvents()
    win.status_label.setText("就绪")
    app.processEvents()

    out_dir = ROOT / "docs" / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    main_png = out_dir / "desktop-main.png"
    assert win.grab().save(str(main_png))

    win.nav.setCurrentRow(5)  # 设置
    app.processEvents()
    settings_png = out_dir / "desktop-settings.png"
    assert win.grab().save(str(settings_png))

    win.close()
    win.deleteLater()
    app.processEvents()

    for p in (main_png, settings_png):
        print(f"{p.relative_to(ROOT)}  {p.stat().st_size} bytes")


if __name__ == "__main__":
    main()
