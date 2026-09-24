from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core.rewatermark import (
    RewatermarkError,
    _delogo_filters,
    inpaint_image,
    validate_boxes,
)
from core.safeio import part_path


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


def test_validate_boxes_wrong_arity():
    with pytest.raises(RewatermarkError, match="区域格式无效"):
        validate_boxes([(0, 0, 10)], 100, 100)
    with pytest.raises(RewatermarkError, match="区域格式无效"):
        validate_boxes([(0, 0, 10, 10, 5)], 100, 100)


def test_validate_boxes_clamps_out_of_bounds():
    assert validate_boxes([(-5, -5, 500, 500)], 100, 80) == [(0, 0, 100, 80)]


def test_validate_boxes_negative_span_clamped_then_rejected():
    # inverted box clamps to min size then still fails the 2px rule
    with pytest.raises(RewatermarkError):
        validate_boxes([(50, 50, 10, 10)], 100, 100)


def test_delogo_filters_include_margin():
    s = _delogo_filters([(4, 4, 14, 14)])
    assert s.startswith("delogo=")
    assert "x=3" in s
    assert "y=3" in s
    assert "w=12" in s
    assert "h=12" in s


def test_delogo_filters_multiple_boxes():
    s = _delogo_filters([(2, 2, 8, 8), (20, 20, 30, 30)])
    assert s.count("delogo=") == 2
    assert "," in s


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


def test_inpaint_inplace(tmp_path: Path):
    src = tmp_path / "wm.png"
    Image.new("RGB", (32, 32), (200, 200, 200)).save(src)
    out = inpaint_image(src, src, [(2, 2, 10, 10)])
    assert out == src
    assert not part_path(src).exists()
