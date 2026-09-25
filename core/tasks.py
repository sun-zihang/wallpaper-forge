from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path


class OutputMode(enum.Enum):
    BESIDE = "beside"
    UNIFIED = "unified"


class TaskKind(enum.Enum):
    IMAGE_CONVERT = "image_convert"
    IMAGE_EDIT = "image_edit"
    VIDEO_CONVERT = "video_convert"
    VIDEO_TO_GIF = "video_to_gif"
    VIDEO_EXTRACT_FRAMES = "video_extract_frames"
    VIDEO_TRIM = "video_trim"
    GIF_SPLIT = "gif_split"
    GIF_MERGE = "gif_merge"
    UNPACK_PKG = "unpack_pkg"
    UNPACK_TEX = "unpack_tex"
    UNPACK_MPKG = "unpack_mpkg"
    INPAINT_IMAGE = "inpaint_image"
    REMOVE_VIDEO_WATERMARK = "remove_video_watermark"


@dataclass
class Task:
    sources: list[Path]
    kind: TaskKind
    params: dict = field(default_factory=dict)
    output_mode: OutputMode = OutputMode.BESIDE
    unified_dir: Path | None = None
    outputs: list[Path] = field(default_factory=list)
    status: str = "pending"
    error: str | None = None


def _unique_force(
    path: Path,
    taken: set[Path],
    protected: Path | None,
    *,
    overwrite: bool = False,
) -> Path:
    n = 0
    while True:
        cand = path if n == 0 else path.with_name(f"{path.stem} ({n}){path.suffix}")
        if overwrite:
            ok = cand.resolve() not in taken
        else:
            ok = not cand.exists() and cand.resolve() not in taken
            if protected is not None and cand.resolve() == protected:
                ok = False
        if ok:
            taken.add(cand.resolve())
            return cand
        n += 1


def resolve_outputs(
    sources: list[Path],
    ext: str,
    output_mode: OutputMode,
    unified_dir: Path | None,
    op_subdir: str = "converted",
    *,
    overwrite: bool = False,
) -> list[Path]:
    ext = ext.lstrip(".").lower()
    taken: set[Path] = set()
    outs: list[Path] = []
    for src in sources:
        if output_mode is OutputMode.UNIFIED:
            if unified_dir is None:
                raise ValueError("unified_dir required for UNIFIED mode")
            base = unified_dir / f"{src.stem}.{ext}"
        else:
            base = src.parent / op_subdir / f"{src.stem}.{ext}"
        outs.append(_unique_force(base, taken, src.resolve(), overwrite=overwrite))
    return outs


def resolve_out_dir(
    src: Path,
    output_mode: OutputMode,
    unified_dir: Path | None,
    *,
    name_suffix: str = "",
    overwrite: bool = False,
    taken: set[Path] | None = None,
) -> Path:
    """Pick a per-source output directory (unpack / frame sequences).

    Default (overwrite=False): an existing non-empty directory is treated as a
    conflict and the next candidate gets a `` (n)`` suffix, so previous runs are
    never touched. Empty directories (e.g. from an interrupted run) are reused.
    overwrite=True reuses an existing directory in place (same-named files
    inside may be replaced by the extraction).
    """
    stem = f"{src.stem}{name_suffix}"
    if output_mode is OutputMode.UNIFIED:
        if unified_dir is None:
            raise ValueError("unified_dir required for UNIFIED mode")
        base = unified_dir / stem
    else:
        base = src.parent / "converted" / stem
    if taken is None:
        taken = set()
    if overwrite and base.exists() and base.is_dir() and base.resolve() not in taken:
        taken.add(base.resolve())
        return base
    n = 1
    cand = base
    while True:
        if overwrite:
            conflict = cand.resolve() in taken or (cand.exists() and not cand.is_dir())
        else:
            conflict = cand.resolve() in taken or (
                cand.exists() and (not cand.is_dir() or any(cand.iterdir()))
            )
        if not conflict:
            taken.add(cand.resolve())
            return cand
        cand = base.with_name(f"{stem} ({n})")
        n += 1


def would_overwrite_sources(
    sources: list[Path],
    outputs: list[Path],
) -> list[tuple[Path, Path]]:
    src_res = {s.resolve(): s for s in sources}
    pairs: list[tuple[Path, Path]] = []
    for o in outputs:
        key = o.resolve()
        if key in src_res:
            pairs.append((src_res[key], o))
    return pairs
