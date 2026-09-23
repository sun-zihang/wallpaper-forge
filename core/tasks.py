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
        if n == 0:
            cand = path
        else:
            cand = path.with_name(f"{path.stem} ({n}){path.suffix}")
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
