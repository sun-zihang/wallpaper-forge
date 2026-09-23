from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path


class WePkgError(Exception):
    pass


@dataclass(frozen=True)
class PkgEntry:
    name: str
    offset: int
    length: int


def _read_u32(data: bytes, pos: int) -> tuple[int, int]:
    if pos + 4 > len(data):
        raise WePkgError("PKG 文件损坏：读取长度字段失败")
    return struct.unpack_from("<I", data, pos)[0], pos + 4


def read_pkg_index(data: bytes) -> tuple[str, list[PkgEntry]]:
    """Parse a Wallpaper Engine PKG index.

    Layout (little-endian):
      u32 header_len | header bytes | u32 file_count
      then file_count times: u32 name_len | name | u32 offset | u32 length
    """
    if len(data) < 8:
        raise WePkgError("PKG 文件过小")
    header_len, pos = _read_u32(data, 0)
    if header_len > len(data) - 4:
        raise WePkgError("不是有效的 Wallpaper Engine 包（头部长度异常）")
    header = data[pos : pos + header_len]
    pos += header_len
    try:
        magic = header.decode("utf-8", errors="ignore").strip("\x00")
    except Exception:
        magic = ""
    if header_len and not (magic.upper().startswith("PKG") or magic.upper().startswith("PKGM")):
        # still attempt parse — some builds embed project path instead
        if header_len > 1024:
            raise WePkgError(f"不是有效的 Wallpaper Engine 包（头部: {magic[:40]!r}）")
    count, pos = _read_u32(data, pos)
    if count > 1_000_000:
        raise WePkgError("不是有效的 Wallpaper Engine 包（文件数异常）")
    entries: list[PkgEntry] = []
    for _ in range(count):
        name_len, pos = _read_u32(data, pos)
        if name_len > 4096 or pos + name_len + 8 > len(data):
            raise WePkgError("PKG 索引损坏")
        raw_name = data[pos : pos + name_len]
        pos += name_len
        name = raw_name.decode("utf-8", errors="replace").rstrip("\x00").replace("\\", "/")
        offset, pos = _read_u32(data, pos)
        length, pos = _read_u32(data, pos)
        entries.append(PkgEntry(name=name, offset=offset, length=length))
    return magic, entries


def extract_pkg(
    src: Path,
    out_dir: Path,
    *,
    cancel_event=None,
    progress_cb=None,
) -> list[Path]:
    data = src.read_bytes()
    _, entries = read_pkg_index(data)
    data_start = _index_end(data)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    total = len(entries)
    for i, entry in enumerate(entries, start=1):
        if cancel_event is not None and cancel_event.is_set():
            raise WePkgError("已取消")
        # Entry offsets are relative to the data block that follows the index.
        start = data_start + entry.offset
        end = start + entry.length
        if entry.length < 0 or start < 0 or end > len(data):
            # Some packages store absolute offsets from file start.
            start, end = entry.offset, entry.offset + entry.length
            if end > len(data) or start < 0:
                raise WePkgError(f"条目越界: {entry.name}")
        blob = data[start:end]
        rel = entry.name.lstrip("/")
        target = out_dir / rel
        try:
            target.resolve().relative_to(out_dir.resolve())
        except ValueError as e:
            raise WePkgError(f"非法路径: {entry.name}") from e
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
        written.append(target)
        if progress_cb:
            progress_cb(i, total)
    return written


def _index_end(data: bytes) -> int:
    header_len, pos = _read_u32(data, 0)
    pos += header_len
    count, pos = _read_u32(data, pos)
    for _ in range(count):
        name_len, pos = _read_u32(data, pos)
        pos += name_len + 8
    return pos
