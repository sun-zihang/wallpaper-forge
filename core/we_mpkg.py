from __future__ import annotations

import re
import struct
from pathlib import Path

from core.we_pkg import WePkgError, extract_pkg, read_pkg_index
from core.we_tex import extract_embedded


class WeMpkgError(Exception):
    pass


_MAGICS = (b"PKGM0014", b"PKGM0015", b"PKGM0016", b"PKGM0017", b"PKGM0018", b"PKGM0019")
_FTYP = b"ftyp"


def _extract_mp4_blobs(data: bytes) -> list[bytes]:
    """Fallback: carve all top-level MP4 (ftyp) boxes out of the buffer."""
    out: list[bytes] = []
    idx = 0
    while True:
        i = data.find(_FTYP, idx)
        if i < 0:
            break
        if i >= 4:
            size = struct.unpack_from(">I", data, i - 4)[0]
            start = i - 4
            if size >= 8 and start + size <= len(data):
                blob = data[start : start + size]
                # extend if size field is only the ftyp box: try to find next moov/mdat heuristic
                out.append(_extend_mp4(data, start, start + size))
                idx = i + 4
                continue
        idx = i + 4
    # de-dup overlapping
    return _dedup(out)


def _extend_mp4(data: bytes, start: int, ftyp_end: int) -> bytes:
    """If only ftyp box captured, try to include following boxes until a reasonable end."""
    pos = ftyp_end
    while pos + 8 <= len(data):
        size = struct.unpack_from(">I", data, pos)[0]
        typ = data[pos + 4 : pos + 8]
        if size < 8 or pos + size > len(data):
            break
        pos += size
        if typ in (b"moov", b"mdat", b"free", b"wide", b"skip", b"pnot"):
            # keep going through standard boxes
            if typ == b"moov":
                break  # moov often last-ish; include it then stop after mdat+moov seen
    if pos <= ftyp_end:
        # no clear structure — scan for mdat/moov after ftyp
        for marker in (b"moov", b"mdat"):
            j = data.find(marker, ftyp_end)
            if j >= 4:
                end = j - 4 + struct.unpack_from(">I", data, j - 4)[0]
                if end <= len(data) and end > start:
                    pos = max(pos, end)
        if pos <= ftyp_end:
            pos = min(len(data), ftyp_end + 4096)
    return data[start:pos]


def _dedup(blobs: list[bytes]) -> list[bytes]:
    kept: list[bytes] = []
    spans: list[tuple[int, int]] = []
    # re-scan is hard without offsets; keep longest unique payloads
    seen: set[bytes] = set()
    for b in sorted(blobs, key=len, reverse=True):
        if b in seen:
            continue
        # skip blobs fully contained in an already kept larger blob
        if any(b in k for k in kept):
            continue
        seen.add(b)
        kept.append(b)
    kept.sort(key=len, reverse=True)
    return kept


def is_mpkg(data: bytes) -> bool:
    head = data[:64]
    return any(m in head for m in _MAGICS) or head.startswith(b"PKGM")


def extract_mpkg(src: Path, out_dir: Path, *, cancel_event=None) -> list[Path]:
    """Extract an MPKG package to out_dir.

    Strategy:
    1. Try PKG-style index parse (MPKG often shares the layout with a different magic).
    2. Carve embedded MP4 / convert TEX entries when present.
    3. As a last resort, carve MP4 boxes directly from the whole file.
    """
    data = src.read_bytes()
    if len(data) < 16:
        raise WeMpkgError("MPKG 文件过小")
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # Attempt 1: structured parse
    try:
        magic, entries = read_pkg_index(data)
        # If index parse produced reasonable entries, use extract_pkg path
        if entries and len(entries) < 500_000:
            try:
                files = extract_pkg(src, out_dir, cancel_event=cancel_event)
                written.extend(_post_process(files, out_dir))
                if written:
                    return _unique_list(written)
            except WePkgError:
                pass
    except WePkgError:
        pass

    if cancel_event is not None and cancel_event.is_set():
        raise WeMpkgError("已取消")

    # Attempt 2: carve media signatures across the file
    carved: list[tuple[str, bytes]] = []
    for ext, payload in _carve_media(data):
        carved.append((ext, payload))

    if not carved:
        raise WeMpkgError(
            "无法从 MPKG 中提取内容：未知加密或版本，请确认是 Wallpaper Engine 导出的 .mpkg"
        )

    for i, (ext, payload) in enumerate(carved, start=1):
        if cancel_event is not None and cancel_event.is_set():
            raise WeMpkgError("已取消")
        name = f"extracted_{i:02d}{ext}"
        target = out_dir / name
        target.write_bytes(payload)
        written.append(target)
    return written


def _post_process(files: list[Path], out_dir: Path) -> list[Path]:
    out: list[Path] = []
    for p in files:
        if p.suffix.lower() == ".tex":
            from core.we_tex import extract_tex

            try:
                got = extract_tex(p, p.with_suffix(""), overwrite=True)
                if got.suffix.lower() != ".tex" and got != p:
                    p.unlink(missing_ok=True)
                out.append(got)
            except Exception:
                out.append(p)
        else:
            out.append(p)
    return out


def _carve_media(data: bytes) -> list[tuple[str, bytes]]:
    results: list[tuple[str, bytes]] = []
    # MP4
    for blob in _extract_mp4_blobs(data):
        results.append((".mp4", blob))
    # Images via TEX-like scan on whole buffer
    ext, payload = extract_embedded(data)
    if ext and ext != ".mp4" and payload:
        results.append((ext, payload))
    # Also pull any standalone PNG not already covered
    sig = b"\x89PNG\r\n\x1a\n"
    idx = 0
    while True:
        i = data.find(sig, idx)
        if i < 0:
            break
        # read until IEND
        iend = data.find(b"IEND", i)
        end = iend + 8 if iend != -1 else min(len(data), i + 64 * 1024)
        if end <= len(data):
            blob = data[i:end]
            if not any(blob == p for _, p in results):
                results.append((".png", blob))
        idx = i + 1
    return results


def _unique_list(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:
        rp = p.resolve() if p.exists() else p
        if rp in seen:
            continue
        seen.add(rp)
        out.append(p)
    return out
