from __future__ import annotations

import threading
from pathlib import Path

from PIL import Image, ImageSequence

from core.safeio import cleanup_part, needs_part, part_path, replace_part


class GifOpError(Exception):
    pass


def split_gif(
    src: Path,
    out_dir: Path,
    *,
    step: int = 1,
    cancel_event: threading.Event | None = None,
    clean_existing: bool = False,
) -> list[Path]:
    """Split a GIF into PNG frames inside out_dir.

    clean_existing=True first removes previous ``frame_*.png`` files in
    out_dir so a reused output directory never mixes frames from different
    runs (foreign files are left untouched).
    """
    if step < 1:
        raise GifOpError("抽稀步长至少为 1")
    try:
        im = Image.open(src)
        im.load()
    except Exception as e:
        raise GifOpError(f"无法读取 GIF: {src.name}（{e}）") from e
    out_dir.mkdir(parents=True, exist_ok=True)
    if clean_existing:
        for old in out_dir.glob("frame_*.png"):
            if old.is_file():
                old.unlink(missing_ok=True)
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
            # with 关闭源文件句柄：同路径 replace 目标时 Windows 上句柄未关会拒绝访问
            with Image.open(p) as im:
                im.load()
                frames.append(im.convert("RGBA"))
        except Exception as e:
            raise GifOpError(f"无法读取图片: {p.name}（{e}）") from e
        _ = i  # loop counter for cancel granularity
    if reverse:
        frames = list(reversed(frames))
    dst.parent.mkdir(parents=True, exist_ok=True)
    same = any(needs_part(p, dst) for p in sources)
    if not same:
        frames[0].save(
            dst,
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=loop,
            optimize=False,
        )
        return dst
    part = part_path(dst)
    # .part 无已知扩展名，PIL 无法推断格式，显式指定（同 Task 2 image_ops）
    fmt = Image.registered_extensions().get(dst.suffix.lower())
    try:
        frames[0].save(
            part,
            format=fmt,
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=loop,
            optimize=False,
        )
    except BaseException:
        cleanup_part(part)
        raise
    replace_part(part, dst)
    return dst
