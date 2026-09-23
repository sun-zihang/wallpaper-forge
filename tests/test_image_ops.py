from PIL import Image

from core.annotate import (
    ImageOpError,
    add_image_watermark,
    add_text_watermark,
    crop_image,
)
from core.image_ops import convert_image


def test_png_to_jpg(png_64, tmp_path):
    out = convert_image(png_64, tmp_path / "o.jpg", quality=80)
    im = Image.open(out)
    assert im.format == "JPEG"
    assert im.size == (64, 48)


def test_max_width_downscale(png_64, tmp_path):
    out = convert_image(png_64, tmp_path / "o.png", max_width=32)
    assert Image.open(out).size == (32, 24)


def test_bad_suffix_raises(png_64, tmp_path):
    try:
        convert_image(png_64, tmp_path / "o.xyz")
        raise AssertionError("should raise")
    except ImageOpError:
        pass


def test_crop(png_64, tmp_path):
    out = crop_image(png_64, tmp_path / "c.png", (0, 0, 32, 24))
    assert Image.open(out).size == (32, 24)


def test_crop_out_of_bounds(png_64, tmp_path):
    try:
        crop_image(png_64, tmp_path / "c.png", (0, 0, 999, 999))
        raise AssertionError("should raise")
    except ImageOpError:
        pass


def test_text_watermark(png_64, tmp_path):
    out = add_text_watermark(png_64, tmp_path / "w.png", text="测试")
    assert Image.open(out).size == (64, 48)


def test_image_watermark(png_64, tmp_path):
    mark = tmp_path / "m.png"
    Image.new("RGBA", (8, 8), (255, 0, 0, 200)).save(mark)
    out = add_image_watermark(png_64, tmp_path / "w2.png", mark=mark, scale=0.5)
    assert Image.open(out).size == (64, 48)
