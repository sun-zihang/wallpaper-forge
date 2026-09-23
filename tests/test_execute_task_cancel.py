import threading
from pathlib import Path

import pytest
from PIL import Image

from core.tasks import Task, TaskKind
from gui.workers import execute_task


def _png(tmp_path: Path, name: str) -> Path:
    p = tmp_path / name
    Image.new("RGB", (8, 8), (1, 2, 3)).save(p)
    return p


def test_image_convert_cancel_before_start(tmp_path: Path):
    src = _png(tmp_path, "a.png")
    out = tmp_path / "a.jpg"
    ev = threading.Event()
    ev.set()
    task = Task(
        sources=[src],
        kind=TaskKind.IMAGE_CONVERT,
        params={"quality": 90, "cancel_event": ev},
        outputs=[out],
    )
    with pytest.raises(RuntimeError, match="已取消"):
        execute_task(task)


def test_progress_cb_called_on_image_convert(tmp_path: Path):
    srcs = [_png(tmp_path, f"{i}.png") for i in range(3)]
    outs = [tmp_path / f"{i}.jpg" for i in range(3)]
    seen: list[int] = []
    task = Task(
        sources=srcs,
        kind=TaskKind.IMAGE_CONVERT,
        params={"quality": 80},
        outputs=outs,
    )
    execute_task(task, progress_cb=seen.append)
    assert seen
    assert seen[-1] == 100
