import os
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture(scope="session")
def qapp():
    previous_platform = os.environ.get("QT_QPA_PLATFORM")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    app = QtWidgets.QApplication.instance()
    if app is None:
        try:
            app = QtWidgets.QApplication([])
        except Exception as exc:
            pytest.skip(f"Qt offscreen platform is unavailable: {exc}")
    if app.platformName() != "offscreen":
        pytest.skip(f"Qt offscreen platform is unavailable: {app.platformName()}")
    yield app
    if previous_platform is None:
        os.environ.pop("QT_QPA_PLATFORM", None)
    else:
        os.environ["QT_QPA_PLATFORM"] = previous_platform


@pytest.fixture
def png_64(tmp_path: Path) -> Path:
    p = tmp_path / "img.png"
    Image.new("RGB", (64, 48), (10, 20, 30)).save(p)
    return p


@pytest.fixture
def gif_2f(tmp_path: Path) -> Path:
    p = tmp_path / "a.gif"
    frames = [Image.new("RGB", (16, 16), (i * 40, 0, 0)) for i in range(2)]
    frames[0].save(p, save_all=True, append_images=frames[1:], duration=100, loop=0)
    return p
