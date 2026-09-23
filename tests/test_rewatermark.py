from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core.rewatermark import (
    RewatermarkError,
    inpaint_image,
    validate_boxes,
)


@pytest.fixture
def watermarked_png(tmp_path: Path) -> Path:
    p = tmp_path / "wm.png"
    im = Image.new("RGB", (64, 48), (30, 100, 200))
    d = ImageDraw.Draw(im)
    # solid watermark block
    d.rectangle((40, 4, 60, 14), fill=(255, 255, 255))
    d.rectangle((41, 5, 59, 13), fill=(0, 0, 0))
    im.save(p)
    return p


def test_validate_boxes_ok():
    assert validate_boxes([(0, 0, 10, 10)], 100, 100) == [(0, 0, 10, 10)]


def test_validate_boxes_empty():
    with pytest.raises(RewatermarkError):
        validate_boxes([], 100, 100)


def test_validate_boxes_too_small():
    with pytest.raises(RewatermarkError):
        validate_boxes([(0, 0, 1, 1)], 100, 100)


def test_inpaint_changes_region(watermarked_png, tmp_path):
    box = (38, 2, 62, 16)
    out = inpaint_image(watermarked_png, tmp_path / "clean.png", [box])
    assert out.exists()
    before = Image.open(watermarked_png).convert("RGB")
    after = Image.open(out).convert("RGB")
    assert before.size == after.size
    # center of watermark should no longer be pure black/white square
    px = after.getpixel((50, 9))
    orig = before.getpixel((50, 9))
    assert px != orig
    # outside region roughly unchanged
    assert after.getpixel((5, 5)) == before.getpixel((5, 5))
