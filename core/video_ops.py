from __future__ import annotations

import re
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

from core.ffmpeg_finder import find_ffmpeg
from core.safeio import cleanup_part, needs_part, part_path, replace_part

VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv"}
# ffmpeg 需在输出为 .part（无法从扩展名推断容器）时显式 -f
FFMPEG_FORMATS = {".mp4": "mp4", ".webm": "webm", ".mov": "mov", ".mkv": "matroska"}


class VideoOpError(Exception):
    def __init__(self, message: str, stderr_tail: str = ""):
        super().__init__(message)
        self.stderr_tail = stderr_tail


ProgressCb = Callable[[int], None]


def run_ffmpeg(
    args: list[str],
    *,
    timeout: int = 600,
    cancel_event: threading.Event | None = None,
    progress_cb: ProgressCb | None = None,
    duration: float | None = None,
    cleanup: Path | None = None,
) -> None:
    ff = find_ffmpeg()
    use_progress = progress_cb is not None and duration and duration > 0
    extra: list[str] = []
    if use_progress:
        # writes machine-readable progress to stdout instead of stderr spam
        extra = ["-progress", "pipe:1", "-nostats"]
    cmd = [str(ff), "-y", "-hide_banner", *extra, *args]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE if use_progress else subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except OSError as e:
        raise VideoOpError(f"无法启动 ffmpeg: {e}") from e

    stderr_lines: list[str] = []
    last_pct = -1
    kill_reason: str | None = None

    def _read_stderr() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            stderr_lines.append(line)

    import threading as _threading

    err_t = _threading.Thread(target=_read_stderr, daemon=True)
    err_t.start()

    try:
        if use_progress and proc.stdout is not None:
            for line in proc.stdout:
                if cancel_event is not None and cancel_event.is_set():
                    kill_reason = "已取消"
                    proc.kill()
                    break
                key, _, val = line.partition("=")
                key = key.strip()
                if key == "out_time_us":
                    try:
                        secs = int(float(val)) / 1_000_000.0
                        pct = int(max(0, min(100, secs * 100.0 / float(duration))))
                        if pct != last_pct:
                            last_pct = pct
                            if progress_cb:
                                progress_cb(pct)
                    except (ValueError, ZeroDivisionError):
                        pass
                elif key == "progress" and val.strip() == "end" and progress_cb:
                    progress_cb(100)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        else:
            # no progress parsing: poll until exit so cancel still works
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    kill_reason = "已取消"
                    proc.kill()
                    break
                try:
                    proc.wait(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    continue

        err_t.join(timeout=2)
        stderr_text = "".join(stderr_lines)
        tail = "\n".join(stderr_text.strip().splitlines()[-8:])
        if kill_reason is not None:
            _cleanup_partial(cleanup)
            raise VideoOpError("已取消", tail)
        if proc.returncode not in (0, None):
            _cleanup_partial(cleanup)
            if cancel_event is not None and cancel_event.is_set():
                raise VideoOpError("已取消", tail)
            raise VideoOpError("FFmpeg 编码失败", tail)
        if use_progress and progress_cb:
            progress_cb(100)
    finally:
        if proc.poll() is None:
            proc.kill()


def _cleanup_partial(path: Path | None) -> None:
    if path is None:
        return
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass


def probe_video_duration(src: Path) -> float | None:
    try:
        ff = find_ffmpeg()
    except Exception:
        return None
    try:
        r = subprocess.run(
            [str(ff), "-hide_banner", "-i", str(src)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    m = re.search(
        r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",
        (r.stderr or "") + (r.stdout or ""),
    )
    if not m:
        return None
    h, mnt, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mnt * 60 + s


def convert_video(
    src: Path,
    dst: Path,
    *,
    keep_audio: bool = True,
    cancel_event: threading.Event | None = None,
    progress_cb: ProgressCb | None = None,
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
    same = needs_part(src, dst)
    target = part_path(dst) if same else dst
    if same:
        args += ["-f", FFMPEG_FORMATS[ext]]
    args.append(str(target))
    run_ffmpeg(
        args,
        cancel_event=cancel_event,
        progress_cb=progress_cb,
        duration=probe_video_duration(src),
        cleanup=target,
    )
    if same:
        # run_ffmpeg 失败时已 cleanup；成功才 replace（0 字节视为失败，避免覆盖源文件）
        if not target.is_file() or target.stat().st_size == 0:
            cleanup_part(target)
            raise VideoOpError(f"输出为空: {dst.name}")
        replace_part(target, dst)
    return dst


def video_to_gif(
    src: Path,
    dst: Path,
    *,
    max_duration: float | None = None,
    fps: int = 15,
    width: int = 480,
    cancel_event: threading.Event | None = None,
    progress_cb: ProgressCb | None = None,
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
    total = max_duration if max_duration and max_duration > 0 else probe_video_duration(src)
    run_ffmpeg(
        args,
        cancel_event=cancel_event,
        progress_cb=progress_cb,
        duration=total,
        cleanup=dst,
    )
    return dst


def extract_frames(
    src: Path,
    out_dir: Path,
    *,
    every_seconds: float | None = None,
    at_seconds: list[float] | None = None,
    ext: str = "png",
    cancel_event: threading.Event | None = None,
    clean_existing: bool = False,
) -> list[Path]:
    """Extract frames into out_dir.

    clean_existing=True first removes previous ``frame_*`` / ``at_*`` image
    files in out_dir so a reused output directory never mixes frames from
    different runs (foreign files are left untouched).
    """
    ext = ext.lstrip(".").lower()
    if ext not in {"png", "jpg", "jpeg", "webp"}:
        raise VideoOpError(f"不支持的截帧格式: {ext}")
    out_dir.mkdir(parents=True, exist_ok=True)
    if clean_existing:
        image_exts = {".png", ".jpg", ".jpeg", ".webp"}
        for old in out_dir.iterdir():
            if not old.is_file() or old.suffix.lower() not in image_exts:
                continue
            if old.name.startswith(("frame_", "at_")):
                old.unlink(missing_ok=True)
    pattern = str(out_dir / f"frame_%04d.{ext}")
    if at_seconds:
        outs: list[Path] = []
        for i, t in enumerate(at_seconds, start=1):
            if cancel_event is not None and cancel_event.is_set():
                raise VideoOpError("已取消")
            if t < 0:
                raise VideoOpError("截帧时间不能为负")
            p = out_dir / f"at_{t:g}s_{i:02d}.{ext}"
            run_ffmpeg(
                ["-ss", str(t), "-i", str(src), "-frames:v", "1", str(p)],
                cancel_event=cancel_event,
                cleanup=p,
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
    progress_cb: ProgressCb | None = None,
) -> Path:
    if start < 0 or end <= start:
        raise VideoOpError("片段范围无效：结束时间必须大于开始时间且非负")
    dst.parent.mkdir(parents=True, exist_ok=True)
    same = needs_part(src, dst)
    target = part_path(dst) if same else dst
    args = [
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
    ]
    if same:
        fmt = FFMPEG_FORMATS.get(dst.suffix.lower())
        if fmt:
            args += ["-f", fmt]
    args.append(str(target))
    run_ffmpeg(
        args,
        cancel_event=cancel_event,
        progress_cb=progress_cb,
        duration=max(0.01, end - start),
        cleanup=target,
    )
    if same:
        # run_ffmpeg 失败时已 cleanup；成功才 replace（0 字节视为失败，避免覆盖源文件）
        if not target.is_file() or target.stat().st_size == 0:
            cleanup_part(target)
            raise VideoOpError(f"输出为空: {dst.name}")
        replace_part(target, dst)
    return dst
