from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from core import gif_ops, image_ops, video_ops
from core.annotate import ImageOpError, add_image_watermark, add_text_watermark, crop_image
from core.ffmpeg_finder import FFmpegNotFound
from core.gif_ops import GifOpError
from core.tasks import Task, TaskKind
from core.video_ops import VideoOpError

_ERROR_MAP = [
    (FileNotFoundError, "文件不存在"),
    (PermissionError, "没有文件访问权限"),
    (FFmpegNotFound, "未找到 FFmpeg"),
    (ImageOpError, "图片处理失败"),
    (GifOpError, "GIF 处理失败"),
    (VideoOpError, "视频处理失败"),
    (ValueError, "参数无效"),
    (OSError, "磁盘或文件系统错误"),
]


def friendly_error(e: BaseException) -> str:
    for typ, label in _ERROR_MAP:
        if isinstance(e, typ):
            detail = str(e).strip()
            if detail and not detail.startswith(label) and detail != label:
                return f"{label}：{detail}"
            return detail if detail else label
    return f"未知错误：{e}"


def execute_task(task: Task) -> None:
    kind = task.kind
    params = dict(task.params)
    cancel_event: threading.Event | None = params.pop("cancel_event", None)

    if kind is TaskKind.IMAGE_CONVERT:
        for s, o in zip(task.sources, task.outputs):
            image_ops.convert_image(
                s,
                o,
                max_width=params.get("max_width") or None,
                quality=int(params.get("quality", 90)),
            )
    elif kind is TaskKind.IMAGE_EDIT:
        op = params.pop("op")
        for s, o in zip(task.sources, task.outputs):
            if op == "crop":
                crop_image(s, o, tuple(params["box"]))
            elif op == "text_watermark":
                add_text_watermark(s, o, **params)
            elif op == "image_watermark":
                add_image_watermark(s, o, **params)
            else:
                raise ImageOpError(f"未知编辑操作: {op}")
    elif kind is TaskKind.VIDEO_CONVERT:
        for s, o in zip(task.sources, task.outputs):
            video_ops.convert_video(
                s, o, keep_audio=params.get("keep_audio", True), cancel_event=cancel_event
            )
    elif kind is TaskKind.VIDEO_TO_GIF:
        for s, o in zip(task.sources, task.outputs):
            video_ops.video_to_gif(
                s,
                o,
                max_duration=params.get("max_duration") or None,
                fps=int(params.get("fps", 15)),
                width=int(params.get("width", 480)),
                cancel_event=cancel_event,
            )
    elif kind is TaskKind.VIDEO_EXTRACT_FRAMES:
        task.outputs = video_ops.extract_frames(
            task.sources[0],
            Path(params["out_dir"]),
            every_seconds=params.get("every_seconds") or None,
            at_seconds=params.get("at_seconds") or None,
            ext=params.get("ext", "png"),
            cancel_event=cancel_event,
        )
    elif kind is TaskKind.VIDEO_TRIM:
        video_ops.trim_video(
            task.sources[0],
            task.outputs[0],
            float(params["start"]),
            float(params["end"]),
            cancel_event=cancel_event,
        )
    elif kind is TaskKind.GIF_SPLIT:
        task.outputs = gif_ops.split_gif(
            task.sources[0], Path(params["out_dir"]), step=int(params.get("step", 1))
        )
    elif kind is TaskKind.GIF_MERGE:
        gif_ops.merge_gif(
            task.sources,
            task.outputs[0],
            duration_ms=int(params.get("duration_ms", 100)),
            loop=int(params.get("loop", 0)),
            reverse=bool(params.get("reverse", False)),
        )
    else:
        raise RuntimeError(f"未接入的任务类型: {kind}")


class TaskRunner(QObject):
    """Executes a batch of tasks synchronously; meant to run inside a QThread."""

    progress = Signal(int, int, str)
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
            self.status_text.emit(f"正在处理 {i}/{total}：{name}")
            task.params["cancel_event"] = self._cancel
            try:
                execute_task(task)
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
        self.batch_finished.emit(ok, failed)
        self.status_text.emit(f"完成：成功 {ok}，失败 {failed}")
        return ok, failed
