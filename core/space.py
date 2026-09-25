from __future__ import annotations

import shutil
from pathlib import Path


def _fmt(n: int) -> str:
    mb = n / (1024 * 1024)
    if mb < 1:
        return f"{n} B"
    if mb < 1024:
        return f"{mb:.0f} MB"
    gb = mb / 1024
    if gb < 1024:
        return f"{gb:.1f} GB"
    return f"{gb / 1024:.1f} TB"


def _existing_ancestor(path: Path) -> Path | None:
    probe = Path(path)
    while not probe.exists():
        if probe == probe.parent:
            return None
        probe = probe.parent
    return probe


def free_space_warning(sources: list[Path], outputs: list[Path] | None = None) -> str | None:
    """Return a warning message when free space likely cannot hold the batch.

    Heuristic: needs roughly the total size of the selected sources. Returns
    None when space looks fine or free space cannot be determined (e.g. network
    drives). Callers decide whether to ask the user.
    """
    if not sources:
        return None
    total = 0
    for p in sources:
        try:
            total += Path(p).stat().st_size
        except OSError:
            continue
    if total <= 0:
        return None

    probe: Path | None = None
    for o in outputs or []:
        probe = _existing_ancestor(Path(o))
        if probe is not None:
            break
    if probe is None:
        probe = _existing_ancestor(Path(sources[0]).parent)
    if probe is None:
        return None
    try:
        free = shutil.disk_usage(probe).free
    except OSError:
        return None
    if free < total:
        return (
            f"输出磁盘剩余 {_fmt(free)}，所选文件合计约 {_fmt(total)}，空间可能不足。仍要开始吗？"
        )
    return None
