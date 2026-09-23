import pytest
from pathlib import Path
from PIL import Image


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
