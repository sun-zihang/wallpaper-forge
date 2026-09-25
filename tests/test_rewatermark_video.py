from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core.ffmpeg_finder import ffmpeg_available, find_ffmpeg
from core.rewatermark import (
    RewatermarkError,
    extract_preview_frame,
    probe_video_size,
    remove_video_watermark,
)

pytestmark = pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not found")


@pytest.fixture(scope="module")
def watermarked_video(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("vid")
    img_path = root / "frame.png"
    im = Image.new("RGB", (160, 120), (10, 80, 40))
    d = ImageDraw.Draw(im)
    d.rectangle((110, 8, 150, 24), fill=(255, 255, 255))
    im.save(img_path)
    out = root / "in.mp4"
    ff = str(find_ffmpeg())
    subprocess.run(
        [
            ff,
            "-y",
            "-loop",
            "1",
            "-t",
            "1",
            "-i",
            str(img_path),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    return out


def test_probe_size(watermarked_video):
    w, h = probe_video_size(watermarked_video)
    assert (w, h) == (160, 120)


def test_extract_preview(watermarked_video, tmp_path: Path):
    frame = extract_preview_frame(watermarked_video, tmp_path / "p.jpg")
    assert frame.is_file() and frame.stat().st_size > 0


def test_remove_video_watermark(watermarked_video, tmp_path: Path):
    out = tmp_path / "clean.mp4"
    boxes = [(100, 4, 155, 28)]
    remove_video_watermark(watermarked_video, out, boxes, frame_width=160, frame_height=120)
    assert out.is_file() and out.stat().st_size > 0
    w, h = probe_video_size(out)
    assert (w, h) == (160, 120)


def test_remove_too_close_to_border(watermarked_video, tmp_path: Path):
    with pytest.raises(RewatermarkError):
        remove_video_watermark(
            watermarked_video,
            tmp_path / "x.mp4",
            [(0, 0, 8, 8)],
            frame_width=160,
            frame_height=120,
        )


def test_cancel(watermarked_video, tmp_path: Path):
    ev = threading.Event()
    ev.set()
    with pytest.raises(RewatermarkError):
        remove_video_watermark(
            watermarked_video,
            tmp_path / "c.mp4",
            [(100, 4, 155, 28)],
            frame_width=160,
            frame_height=120,
            cancel_event=ev,
        )
