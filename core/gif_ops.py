from __future__ import annotations

import threading
from pathlib import Path

from PIL import Image, ImageSequence


class GifOpError(Exception):
    pass


def split_gif(
    src: Path,
    out_dir: Path,
    *,
    step: int = 1,
    cancel_event: threading.Event | None = None,
) -> list[Path]:
    if step < 1:
        raise GifOpError("抽稀步长至少为 1")
    try:
        im = Image.open(src)
        im.load()
    except Exception as e:
        raise GifOpError(f"无法读取 GIF: {src.name}（{e}）") from e
    out_dir.mkdir(parents=True, exist_ok=True)
    outs: list[Path] = []
    idx = 0
    kept = 0
    for frame in ImageSequence.Iterator(im):
        if cancel_event is not None and cancel_event.is_set():
            raise GifOpError("已取消")
        if idx % step == 0:
            kept += 1
            p = out_dir / f"frame_{kept:04d}.png"
            frame.convert("RGBA").save(p)
            outs.append(p)
        idx += 1
    if not outs:
        raise GifOpError("GIF 中没有可导出的帧")
    return outs


def merge_gif(
    sources: list[Path],
    dst: Path,
    *,
    duration_ms: int = 100,
    loop: int = 0,
    reverse: bool = False,
    cancel_event: threading.Event | None = None,
) -> Path:
    if not sources:
        raise GifOpError("没有可合并的图片")
    if duration_ms < 10:
        raise GifOpError("帧间隔至少 10 毫秒")
    frames = []
    for i, p in enumerate(sources):
        if cancel_event is not None and cancel_event.is_set():
            raise GifOpError("已取消")
        try:
            im = Image.open(p)
            im.load()
            frames.append(im.convert("RGBA"))
        except Exception as e:
            raise GifOpError(f"无法读取图片: {p.name}（{e}）") from e
        _ = i  # loop counter for cancel granularity
    if reverse:
        frames = list(reversed(frames))
    dst.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        dst,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=loop,
        optimize=False,
    )
    return dst
