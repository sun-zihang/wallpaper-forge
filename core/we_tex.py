from __future__ import annotations

import struct
from pathlib import Path

PNG_SIG = b"\x89PNG\r\n\x1a\n"
JPEG_SIG = b"\xff\xd8\xff"
WEBP_RIFF = b"RIFF"
MP4_FTYP = b"ftyp"


class WeTexError(Exception):
    pass


def extract_embedded(tex_data: bytes) -> tuple[str, bytes] | tuple[None, None]:
    """Scan a TEX container for an embedded standard image/video payload.

    Returns (ext, payload) with ext like ".png" or None when nothing found.
    Prefers the largest plausible payload when multiple signatures exist.
    """
    candidates: list[tuple[str, int, int]] = []  # ext, start, end

    # PNG with optional u32 length prefix (length covers payload after the field)
    idx = 0
    while True:
        i = tex_data.find(PNG_SIG, idx)
        if i < 0:
            break
        start = i
        end = len(tex_data)
        if i >= 4:
            ln = struct.unpack_from("<I", tex_data, i - 4)[0]
            if 8 <= ln <= len(tex_data) and i + ln <= len(tex_data):
                end = i + ln
        candidates.append((".png", start, end))
        idx = i + 1

    # JPEG
    i = tex_data.find(JPEG_SIG)
    if i >= 0:
        end = len(tex_data)
        if i >= 4:
            ln = struct.unpack_from("<I", tex_data, i - 4)[0]
            if 16 <= ln <= len(tex_data) and i + ln <= len(tex_data):
                end = i + ln
        # trim trailing garbage at EOI if present
        eoi = tex_data.find(b"\xff\xd9", i)
        if eoi != -1 and eoi + 2 <= end:
            end = eoi + 2
        candidates.append((".jpg", i, end))

    # WebP (RIFF....WEBP)
    idx = 0
    while True:
        i = tex_data.find(b"WEBP", idx)
        if i < 0:
            break
        if i >= 4 and tex_data[i - 8 : i - 4] == WEBP_RIFF:
            riff = i - 8
            size = struct.unpack_from("<I", tex_data, riff + 4)[0] + 8
            if riff + size <= len(tex_data):
                candidates.append((".webp", riff, riff + size))
        idx = i + 1

    # MP4 (size + ftyp)
    idx = 0
    while True:
        i = tex_data.find(MP4_FTYP, idx)
        if i < 0:
            break
        if i >= 4:
            box_size = struct.unpack_from(">I", tex_data, i - 4)[0]
            start = i - 4
            if 8 <= box_size <= len(tex_data) - start:
                candidates.append((".mp4", start, start + box_size))
            else:
                candidates.append((".mp4", start, len(tex_data)))
        idx = i + 1

    if not candidates:
        return None, None

    def span(c: tuple[str, int, int]) -> int:
        return c[2] - c[1]

    # Prefer video > image when multiple types (wallpaper main media first)
    priority = {".mp4": 0, ".png": 1, ".webp": 2, ".jpg": 3}
    candidates.sort(key=lambda c: (priority.get(c[0], 9), -span(c)))
    ext, start, end = candidates[0]
    payload = tex_data[start:end]
    if len(payload) < 16:
        return None, None
    return ext, payload


def extract_tex(src: Path, out_base: Path) -> Path:
    """Extract embedded media from a .tex file.

    out_base is a path without forcing extension; we return the actual written path.
    """
    data = src.read_bytes()
    ext, payload = extract_embedded(data)
    if ext and payload:
        dst = out_base.with_suffix(ext)
        n = 1
        while dst.exists():
            dst = out_base.with_name(f"{out_base.stem} ({n}){ext}")
            n += 1
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(payload)
        return dst
    dst = out_base.with_suffix(".tex")
    n = 1
    while dst.exists():
        dst = out_base.with_name(f"{out_base.stem} ({n}).tex")
        n += 1
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    return dst
