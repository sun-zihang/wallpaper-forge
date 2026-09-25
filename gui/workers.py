from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from core import gif_ops, image_ops, video_ops
from core.annotate import ImageOpError, add_image_watermark, add_text_watermark, crop_image
from core.ffmpeg_finder import FFmpegNotFound
from core.gif_ops import GifOpError
from core.rewatermark import (
    RewatermarkError,
    inpaint_image,
    probe_video_size,
    remove_video_watermark,
)
from core.tasks import Task, TaskKind
from core.video_ops import VideoOpError
from core.we_mpkg import WeMpkgError, extract_mpkg
from core.we_pkg import WePkgError, extract_pkg
from core.we_tex import WeTexError, extract_tex

_ERROR_MAP = [
    (FileNotFoundError, "文件不存在"),
    (PermissionError, "没有文件访问权限"),
    (FFmpegNotFound, "未找到 FFmpeg"),
    (ImageOpError, "图片处理失败"),
    (GifOpError, "GIF 处理失败"),
    (VideoOpError, "视频处理失败"),
    (WePkgError, "PKG 解包失败"),
    (WeTexError, "TEX 解析失败"),
    (WeMpkgError, "MPKG 解包失败"),
    (RewatermarkError, "去水印失败"),
    (ValueError, "参数无效"),
    (OSError, "磁盘或文件系统错误"),
]


def friendly_error(e: BaseException) -> str:
    stderr_tail = ""
    if isinstance(e, VideoOpError) and e.stderr_tail:
        stderr_tail = e.stderr_tail.strip()
    for typ, label in _ERROR_MAP:
        if isinstance(e, typ):
            detail = str(e).strip()
            if detail and not detail.startswith(label) and detail != label:
                msg = f"{label}：{detail}"
            else:
                msg = detail if detail else label
            if stderr_tail and "已取消" not in msg:
                last = stderr_tail.splitlines()[-1].strip() if stderr_tail else ""
                if last:
                    msg = f"{msg}（{last}）"
            return msg
    return f"未知错误：{e}"


def _check_cancel(cancel_event: threading.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise RuntimeError("已取消")


def _batch_progress(done: int, total: int) -> int:
    if total <= 0:
        return 100
    return int(done * 100 / total)


def execute_task(
    task: Task,
    *,
    progress_cb: Callable[[int], None] | None = None,
) -> None:
    kind = task.kind
    params = dict(task.params)
    cancel_event: threading.Event | None = params.pop("cancel_event", None)
    n = max(1, len(task.sources))

    def _tick(i: int) -> None:
        if progress_cb:
            progress_cb(_batch_progress(i, n))

    _check_cancel(cancel_event)

    if kind is TaskKind.IMAGE_CONVERT:
        for i, (s, o) in enumerate(zip(task.sources, task.outputs), start=1):
            _check_cancel(cancel_event)
            image_ops.convert_image(
                s,
                o,
                max_width=params.get("max_width") or None,
                quality=int(params.get("quality", 90)),
            )
            _tick(i)
    elif kind is TaskKind.IMAGE_EDIT:
        op = params.pop("op")
        for i, (s, o) in enumerate(zip(task.sources, task.outputs), start=1):
            _check_cancel(cancel_event)
            if op == "crop":
                crop_image(s, o, tuple(params["box"]))
            elif op == "text_watermark":
                add_text_watermark(s, o, **params)
            elif op == "image_watermark":
                add_image_watermark(s, o, **params)
            else:
                raise ImageOpError(f"未知编辑操作: {op}")
            _tick(i)
    elif kind is TaskKind.VIDEO_CONVERT:
        for i, (s, o) in enumerate(zip(task.sources, task.outputs), start=1):
            _check_cancel(cancel_event)
            video_ops.convert_video(
                s,
                o,
                keep_audio=params.get("keep_audio", True),
                cancel_event=cancel_event,
                progress_cb=progress_cb,
            )
            _tick(i)
    elif kind is TaskKind.VIDEO_TO_GIF:
        for i, (s, o) in enumerate(zip(task.sources, task.outputs), start=1):
            _check_cancel(cancel_event)
            video_ops.video_to_gif(
                s,
                o,
                max_duration=params.get("max_duration") or None,
                fps=int(params.get("fps", 15)),
                width=int(params.get("width", 480)),
                cancel_event=cancel_event,
                progress_cb=progress_cb,
            )
            _tick(i)
    elif kind is TaskKind.VIDEO_EXTRACT_FRAMES:
        task.outputs = video_ops.extract_frames(
            task.sources[0],
            Path(params["out_dir"]),
            every_seconds=params.get("every_seconds") or None,
            at_seconds=params.get("at_seconds") or None,
            ext=params.get("ext", "png"),
            cancel_event=cancel_event,
            clean_existing=True,
        )
        _tick(1)
    elif kind is TaskKind.VIDEO_TRIM:
        video_ops.trim_video(
            task.sources[0],
            task.outputs[0],
            float(params["start"]),
            float(params["end"]),
            cancel_event=cancel_event,
            progress_cb=progress_cb,
        )
        _tick(1)
    elif kind is TaskKind.GIF_SPLIT:
        task.outputs = gif_ops.split_gif(
            task.sources[0],
            Path(params["out_dir"]),
            step=int(params.get("step", 1)),
            cancel_event=cancel_event,
            clean_existing=True,
        )
        _tick(1)
    elif kind is TaskKind.GIF_MERGE:
        gif_ops.merge_gif(
            task.sources,
            task.outputs[0],
            duration_ms=int(params.get("duration_ms", 100)),
            loop=int(params.get("loop", 0)),
            reverse=bool(params.get("reverse", False)),
            cancel_event=cancel_event,
        )
        _tick(1)
    elif kind is TaskKind.UNPACK_PKG:
        task.outputs = extract_pkg(
            task.sources[0],
            Path(params["out_dir"]),
            cancel_event=cancel_event,
        )
        _tick(1)
    elif kind is TaskKind.UNPACK_TEX:
        _check_cancel(cancel_event)
        src = task.sources[0]
        out_dir = Path(params["out_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        task.outputs = [extract_tex(src, out_dir / src.stem, overwrite=True)]
        _tick(1)
    elif kind is TaskKind.UNPACK_MPKG:
        task.outputs = extract_mpkg(
            task.sources[0],
            Path(params["out_dir"]),
            cancel_event=cancel_event,
        )
        _tick(1)
    elif kind is TaskKind.INPAINT_IMAGE:
        src, out = task.sources[0], Path(params["out"])
        task.outputs = [inpaint_image(src, out, list(params["boxes"]))]
        _tick(1)
    elif kind is TaskKind.REMOVE_VIDEO_WATERMARK:
        src, out = task.sources[0], Path(params["out"])
        w = params.get("frame_width")
        h = params.get("frame_height")
        if not w or not h:
            w, h = probe_video_size(src)
        task.outputs = [
            remove_video_watermark(
                src,
                out,
                list(params["boxes"]),
                frame_width=int(w),
                frame_height=int(h),
                cancel_event=cancel_event,
                progress_cb=progress_cb,
            )
        ]
        _tick(1)
    else:
        raise RuntimeError(f"未接入的任务类型: {kind}")


class TaskRunner(QObject):
    """Executes a batch of tasks synchronously; meant to run inside a QThread."""

    progress = Signal(int, int, str)
    progress_pct = Signal(int)
    task_finished = Signal(object)
    batch_finished = Signal(int, int)
    status_text = Signal(str)

    def __init__(self):
        super().__init__()
        self._cancel = threading.Event()

    def reset_cancel(self) -> None:
        self._cancel.clear()

    def request_cancel(self) -> None:
        self._cancel.set()

    @property
    def cancel_event(self) -> threading.Event:
        return self._cancel

    def run_batch(self, batch: list[Task]) -> tuple[int, int]:
        ok = failed = 0
        total = len(batch)
        self._cancel.clear()
        for i, task in enumerate(batch, start=1):
            if self._cancel.is_set():
                task.status = "cancelled"
                task.error = "已取消"
                failed += 1
                self.task_finished.emit(task)
                continue
            task.status = "running"
            name = task.sources[0].name if task.sources else ""
            self.progress.emit(i, total, name)
            self.progress_pct.emit(int((i - 1) * 100 / max(1, total)))
            self.status_text.emit(f"正在处理 {i}/{total}：{name}")
            task.params["cancel_event"] = self._cancel
            try:
                base = (i - 1) * 100 / max(1, total)
                span = 100.0 / max(1, total)

                def _pct(p: int, _base: float = base, _span: float = span) -> None:
                    self.progress_pct.emit(int(_base + p * _span / 100.0))

                execute_task(task, progress_cb=_pct)
                if self._cancel.is_set():
                    task.status = "cancelled"
                    task.error = "已取消"
                    failed += 1
                else:
                    task.status = "done"
                    ok += 1
            except Exception as e:
                if self._cancel.is_set() or "已取消" in str(e):
                    task.status = "cancelled"
                    task.error = "已取消"
                else:
                    task.status = "failed"
                    task.error = friendly_error(e)
                failed += 1
            task.params.pop("cancel_event", None)
            self.task_finished.emit(task)
            self.progress_pct.emit(int(i * 100 / max(1, total)))
        self.batch_finished.emit(ok, failed)
        self.status_text.emit(f"完成：成功 {ok}，失败 {failed}")
        return ok, failed
