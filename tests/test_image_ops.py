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
    except ImageOpError as exc:
        assert "裁剪区域无效" in str(exc)


def test_crop_empty_box_raises(png_64, tmp_path):
    for box in ((10, 10, 10, 20), (0, 0, 0, 10), (-1, 0, 10, 10), (0, 5, 10, 5)):
        try:
            crop_image(png_64, tmp_path / "c.png", box)
            raise AssertionError(f"should raise for {box}")
        except ImageOpError as exc:
            assert "裁剪区域无效" in str(exc)


def test_crop_exact_bounds_ok(png_64, tmp_path):
    out = crop_image(png_64, tmp_path / "c.png", (0, 0, 64, 48))
    assert Image.open(out).size == (64, 48)


def test_text_watermark_empty_rejected(png_64, tmp_path):
    try:
        add_text_watermark(png_64, tmp_path / "w.png", text="")
        raise AssertionError("should raise")
    except ImageOpError as exc:
        assert "水印文字不能为空" in str(exc)


def test_text_watermark_unknown_position(png_64, tmp_path):
    try:
        add_text_watermark(
            png_64, tmp_path / "w.png", text="hi", position="bottom_middle"
        )
        raise AssertionError("should raise")
    except ImageOpError as exc:
        assert "未知水印位置" in str(exc)


def test_image_watermark_scale_bounds(png_64, tmp_path):
    mark = tmp_path / "m.png"
    Image.new("RGBA", (8, 8), (255, 0, 0, 200)).save(mark)
    for scale in (0.04, 1.01):
        try:
            add_image_watermark(
                png_64, tmp_path / "w2.png", mark=mark, scale=scale
            )
            raise AssertionError(f"should raise for scale={scale}")
        except ImageOpError as exc:
            assert "水印缩放比例" in str(exc)


def test_image_watermark_opacity_bounds(png_64, tmp_path):
    mark = tmp_path / "m.png"
    Image.new("RGBA", (8, 8), (255, 0, 0, 200)).save(mark)
    for opacity in (-0.01, 1.01):
        try:
            add_image_watermark(
                png_64, tmp_path / "w2.png", mark=mark, scale=0.5, opacity=opacity
            )
            raise AssertionError(f"should raise for opacity={opacity}")
        except ImageOpError as exc:
            assert "透明度" in str(exc)


def test_text_watermark(png_64, tmp_path):
    out = add_text_watermark(png_64, tmp_path / "w.png", text="测试")
    assert Image.open(out).size == (64, 48)


def test_image_watermark(png_64, tmp_path):
    mark = tmp_path / "m.png"
    Image.new("RGBA", (8, 8), (255, 0, 0, 200)).save(mark)
    out = add_image_watermark(png_64, tmp_path / "w2.png", mark=mark, scale=0.5)
    assert Image.open(out).size == (64, 48)


def test_all_five_positions_render(png_64, tmp_path):
    mark = tmp_path / "m.png"
    Image.new("RGBA", (8, 8), (255, 0, 0, 200)).save(mark)
    for pos in (
        "top_left",
        "top_right",
        "bottom_left",
        "bottom_right",
        "center",
    ):
        out = tmp_path / f"w_{pos}.png"
        add_image_watermark(
            png_64, out, mark=mark, scale=0.3, position=pos
        )
        assert Image.open(out).size == (64, 48)
