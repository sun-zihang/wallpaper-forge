from __future__ import annotations

import subprocess
import threading
from pathlib import Path

from core.ffmpeg_finder import find_ffmpeg

VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv"}


class VideoOpError(Exception):
    def __init__(self, message: str, stderr_tail: str = ""):
        super().__init__(message)
        self.stderr_tail = stderr_tail


def run_ffmpeg(
    args: list[str],
    *,
    timeout: int = 600,
    cancel_event: threading.Event | None = None,
) -> None:
    ff = find_ffmpeg()
    cmd = [str(ff), "-y", "-hide_banner", *args]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as e:
        raise VideoOpError(f"无法启动 ffmpeg: {e}") from e
    try:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                proc.kill()
                proc.wait()
                raise VideoOpError("已取消")
            try:
                _, stderr = proc.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                continue
        if proc.returncode != 0:
            tail = "\n".join((stderr or "").strip().splitlines()[-8:])
            if cancel_event is not None and cancel_event.is_set():
                raise VideoOpError("已取消", tail)
            raise VideoOpError("FFmpeg 编码失败", tail)
    finally:
        if proc.poll() is None:
            proc.kill()


def convert_video(
    src: Path,
    dst: Path,
    *,
    keep_audio: bool = True,
    cancel_event: threading.Event | None = None,
) -> Path:
    ext = dst.suffix.lower()
    if ext not in VIDEO_EXTS:
        raise VideoOpError(f"不支持的输出格式: {dst.suffix}")
    if not src.is_file():
        raise VideoOpError(f"输入文件不存在: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if ext == ".webm":
        vcodec, acodec = "libvpx-vp9", "libopus"
    else:
        vcodec, acodec = "libx264", "aac"
    args = ["-i", str(src), "-c:v", vcodec, "-preset", "medium"]
    if keep_audio:
        args += ["-c:a", acodec]
    else:
        args += ["-an"]
    if ext in {".mp4", ".mov"}:
        args += ["-pix_fmt", "yuv420p"]
    args.append(str(dst))
    run_ffmpeg(args, cancel_event=cancel_event)
    return dst


def video_to_gif(
    src: Path,
    dst: Path,
    *,
    max_duration: float | None = None,
    fps: int = 15,
    width: int = 480,
    cancel_event: threading.Event | None = None,
) -> Path:
    if fps < 1 or fps > 50:
        raise VideoOpError("GIF 帧率需在 1–50 之间")
    if width < 16:
        raise VideoOpError("GIF 宽度至少 16 像素")
    dst.parent.mkdir(parents=True, exist_ok=True)
    args: list[str] = []
    if max_duration and max_duration > 0:
        args += ["-t", str(max_duration)]
    args += ["-i", str(src), "-an"]
    vf = (
        f"fps={fps},scale={width}:-1:flags=lanczos,"
        "split[s0][s1];[s0]palettegen=max_colors=128[p];"
        "[s1][p]paletteuse=dither=bayer"
    )
    args += ["-vf", vf, str(dst)]
    run_ffmpeg(args, cancel_event=cancel_event)
    return dst


def extract_frames(
    src: Path,
    out_dir: Path,
    *,
    every_seconds: float | None = None,
    at_seconds: list[float] | None = None,
    ext: str = "png",
    cancel_event: threading.Event | None = None,
) -> list[Path]:
    ext = ext.lstrip(".").lower()
    if ext not in {"png", "jpg", "jpeg", "webp"}:
        raise VideoOpError(f"不支持的截帧格式: {ext}")
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / f"frame_%04d.{ext}")
    if at_seconds:
        outs: list[Path] = []
        for i, t in enumerate(at_seconds, start=1):
            if t < 0:
                raise VideoOpError("截帧时间不能为负")
            p = out_dir / f"at_{t:g}s_{i:02d}.{ext}"
            run_ffmpeg(
                ["-ss", str(t), "-i", str(src), "-frames:v", "1", str(p)],
                cancel_event=cancel_event,
            )
            if p.is_file():
                outs.append(p)
        if not outs:
            raise VideoOpError("未能截取任何帧")
        return outs
    if not every_seconds or every_seconds <= 0:
        raise VideoOpError("请指定截帧间隔（每 N 秒）")
    run_ffmpeg(
        ["-i", str(src), "-vf", f"fps=1/{every_seconds}", pattern],
        cancel_event=cancel_event,
    )
    outs = sorted(out_dir.glob(f"*.{ext}"))
    if not outs:
        raise VideoOpError("未能截取任何帧")
    return outs


def trim_video(
    src: Path,
    dst: Path,
    start: float,
    end: float,
    *,
    cancel_event: threading.Event | None = None,
) -> Path:
    if start < 0 or end <= start:
        raise VideoOpError("片段范围无效：结束时间必须大于开始时间且非负")
    dst.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-ss",
            str(start),
            "-to",
            str(end),
            "-i",
            str(src),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(dst),
        ],
        cancel_event=cancel_event,
    )
    return dst
