from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core.rewatermark import (
    RewatermarkError,
    _delogo_filters,
    extract_preview_frame,
    inpaint_image,
    probe_video_size,
    remove_video_watermark,
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


def test_inpaint_unreadable_source(tmp_path: Path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not-a-png")
    with pytest.raises(RewatermarkError, match="无法解码图片"):
        inpaint_image(bad, tmp_path / "o.png", [(0, 0, 10, 10)])


def test_probe_video_size_unparseable_raises(monkeypatch, tmp_path: Path):
    import subprocess

    from core import ffmpeg_finder

    class _Res:
        stderr = "no WxH here"
        stdout = ""

    monkeypatch.setattr(ffmpeg_finder, "find_ffmpeg", lambda: Path("ff"))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Res())
    with pytest.raises(RewatermarkError, match="无法读取视频分辨率"):
        probe_video_size(tmp_path / "x.mp4")


def test_extract_preview_frame_missing_output(monkeypatch, tmp_path: Path):
    def fake_run_ffmpeg(args, **kwargs):
        return None

    monkeypatch.setattr("core.rewatermark.run_ffmpeg", fake_run_ffmpeg)
    with pytest.raises(RewatermarkError, match="无法提取视频预览帧"):
        extract_preview_frame(tmp_path / "in.mp4", tmp_path / "p.jpg")


def test_remove_video_watermark_empty_output(monkeypatch, tmp_path: Path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x" * 32)

    def fake_run_ffmpeg(args, **kwargs):
        Path(args[-1]).write_bytes(b"")

    monkeypatch.setattr("core.rewatermark.run_ffmpeg", fake_run_ffmpeg)
    import core.video_ops as vops

    monkeypatch.setattr(vops, "probe_video_duration", lambda p: None)
    with pytest.raises(RewatermarkError, match="输出为空"):
        # same path → uses .part; empty part must be cleaned, source preserved
        remove_video_watermark(
            src, src, [(10, 10, 40, 40)], frame_width=100, frame_height=80
        )
    assert src.read_bytes() == b"x" * 32
    assert not part_path(src).exists()

    # different path: raises but empty dst may remain (documented behaviour)
    dst = tmp_path / "out.mp4"
    with pytest.raises(RewatermarkError, match="输出为空"):
        remove_video_watermark(
            src, dst, [(10, 10, 40, 40)], frame_width=100, frame_height=80
        )
    assert dst.exists() and dst.stat().st_size == 0


def test_remove_video_watermark_maps_cancel(monkeypatch, tmp_path: Path):
    from core.video_ops import VideoOpError

    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")

    def boom(*a, **k):
        raise VideoOpError("已取消", "tail")

    monkeypatch.setattr("core.rewatermark.run_ffmpeg", boom)
    import core.video_ops as vops

    monkeypatch.setattr(vops, "probe_video_duration", lambda p: None)
    with pytest.raises(RewatermarkError, match="已取消"):
        remove_video_watermark(
            src, tmp_path / "o.mp4", [(10, 10, 40, 40)], frame_width=100, frame_height=80
        )
