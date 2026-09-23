from __future__ import annotations

import functools
import os
import shutil
import sys
from pathlib import Path


class FFmpegNotFound(RuntimeError):
    pass


def _candidates() -> list[Path]:
    found: list[Path] = []
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).parent
        found += [
            app_dir / "ffmpeg.exe",
            app_dir / "bin" / "ffmpeg.exe",
            app_dir / "_internal" / "ffmpeg.exe",
        ]
    env = os.environ.get("WALLPAPER_FORGE_FFMPEG")
    if env:
        found.append(Path(env))
    here = Path(__file__).resolve().parent.parent
    found.append(here / "vendor" / "ffmpeg" / "ffmpeg.exe")
    which = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if which:
        found.append(Path(which))
    return found


@functools.lru_cache(maxsize=1)
def find_ffmpeg() -> Path:
    for p in _candidates():
        if p and p.is_file():
            return p
    raise FFmpegNotFound(
        "未找到 ffmpeg。请安装 ffmpeg 并加入 PATH，或设置环境变量 WALLPAPER_FORGE_FFMPEG。"
    )


def ffmpeg_available() -> bool:
    try:
        find_ffmpeg()
        return True
    except FFmpegNotFound:
        return False
