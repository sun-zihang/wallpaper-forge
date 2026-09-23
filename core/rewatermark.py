from __future__ import annotations

import threading
from pathlib import Path

import cv2
import numpy as np

from core.video_ops import run_ffmpeg

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


class RewatermarkError(Exception):
    pass


def validate_boxes(
    boxes: list[tuple[int, int, int, int]],
    width: int,
    height: int,
) -> list[tuple[int, int, int, int]]:
    if not boxes:
        raise RewatermarkError("请先框选水印区域")
    cleaned: list[tuple[int, int, int, int]] = []
    for box in boxes:
        if len(box) != 4:
            raise RewatermarkError("区域格式无效")
        l, t, r, b = (int(v) for v in box)
        l = max(0, min(l, width - 1))
        t = max(0, min(t, height - 1))
        r = max(l + 1, min(r, width))
        b = max(t + 1, min(b, height))
        if r - l < 2 or b - t < 2:
            raise RewatermarkError("框选区域过小（宽高至少 2 像素）")
        cleaned.append((l, t, r, b))
    return cleaned


def inpaint_image(
    src: Path,
    dst: Path,
    boxes: list[tuple[int, int, int, int]],
    *,
    radius: int = 3,
) -> Path:
    try:
        img = cv2.imread(str(src), cv2.IMREAD_COLOR)
    except Exception as e:  # noqa: BLE001
        raise RewatermarkError(f"无法解码图片：{src.name}（{e}）") from e
    if img is None:
        raise RewatermarkError(f"无法解码图片：{src.name}")
    h, w = img.shape[:2]
    cleaned = validate_boxes(boxes, w, h)
    mask = np.zeros((h, w), dtype=np.uint8)
    for l, t, r, b in cleaned:
        mask[t:b, l:r] = 255
    try:
        out = cv2.inpaint(img, mask, max(1, radius), cv2.INPAINT_TELEA)
    except Exception as e:  # noqa: BLE001
        raise RewatermarkError(f"修复失败：{e}") from e
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(dst), out):
        raise RewatermarkError(f"保存失败：{dst.name}")
    return dst


def _delogo_filters(boxes: list[tuple[int, int, int, int]]) -> str:
    parts = []
    for l, t, r, b in boxes:
        w = r - l
        h = b - t
        # delogo needs box strictly inside frame with a small margin
        x = max(0, l - 1)
        y = max(0, t - 1)
        parts.append(f"delogo=x={x}:y={y}:w={w + 2}:h={h + 2}")
    return ",".join(parts)


def remove_video_watermark(
    src: Path,
    dst: Path,
    boxes: list[tuple[int, int, int, int]],
    *,
    frame_width: int,
    frame_height: int,
    cancel_event: threading.Event | None = None,
) -> Path:
    cleaned = validate_boxes(boxes, frame_width, frame_height)
    # Ensure delogo boxes stay inside the frame (delogo cannot touch borders)
    safe: list[tuple[int, int, int, int]] = []
    for l, t, r, b in cleaned:
        l = max(1, l)
        t = max(1, t)
        r = min(frame_width - 1, r)
        b = min(frame_height - 1, b)
        if r - l < 2 or b - t < 2:
            raise RewatermarkError("框选区域过小或贴边，请往内侧挪一点")
        safe.append((l, t, r, b))

    dst.parent.mkdir(parents=True, exist_ok=True)
    vf = _delogo_filters(safe)
    args = [
        "-i",
        str(src),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        str(dst),
    ]
    try:
        run_ffmpeg(args, cancel_event=cancel_event)
    except Exception as e:  # VideoOpError / FFmpegNotFound
        if "已取消" in str(e):
            raise RewatermarkError("已取消") from e
        raise RewatermarkError(f"视频处理失败：{e}") from e
    if not dst.is_file() or dst.stat().st_size == 0:
        raise RewatermarkError("视频处理失败：输出为空")
    return dst


def probe_video_size(src: Path) -> tuple[int, int]:
    import subprocess

    from core.ffmpeg_finder import find_ffmpeg

    ff = find_ffmpeg()
    r = subprocess.run(
        [
            str(ff),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(src),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    # ffprobe-style won't work with ffmpeg binary; use ffmpeg -i parse instead
    line = (r.stdout or "") + (r.stderr or "")
    # fallback: run ffmpeg -i and parse
    r2 = subprocess.run([str(ff), "-i", str(src)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    text = r2.stderr or ""
    import re

    m = re.search(r"(\d{2,5})x(\d{2,5})", text)
    if not m:
        raise RewatermarkError("无法读取视频分辨率")
    return int(m.group(1)), int(m.group(2))


def extract_preview_frame(src: Path, dest: Path, *, at: float = 0.0) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        ["-ss", str(at), "-i", str(src), "-frames:v", "1", "-q:v", "2", str(dest)]
    )
    if not dest.is_file():
        raise RewatermarkError("无法提取视频预览帧")
    return dest
