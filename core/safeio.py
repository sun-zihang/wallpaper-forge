from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def part_path(dst: Path) -> Path:
    return dst.with_suffix(dst.suffix + ".part")


def needs_part(src: Path, dst: Path) -> bool:
    try:
        return dst.resolve() == src.resolve()
    except OSError:
        return False


def replace_part(part: Path, dst: Path) -> None:
    os.replace(part, dst)


def cleanup_part(part: Path) -> None:
    try:
        if part.is_file():
            part.unlink()
    except OSError:
        pass


@contextmanager
def staged_dst(src: Path, dst: Path) -> Iterator[Path]:
    """Yield the path to write. If same as src, write .part then replace on success."""
    if not needs_part(src, dst):
        yield dst
        return
    part = part_path(dst)
    part.parent.mkdir(parents=True, exist_ok=True)
    try:
        yield part
    except BaseException:
        cleanup_part(part)
        raise
    else:
        replace_part(part, dst)
