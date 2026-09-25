"""Unit tests for core.we_mpkg carving helpers (no full-package fixtures)."""

from __future__ import annotations

import struct
from pathlib import Path

from core.we_mpkg import (
    WeMpkgError,
    _dedup,
    _extend_mp4,
    _extract_mp4_blobs,
    _unique_list,
    extract_mpkg,
    is_mpkg,
)


def _box(typ: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + typ + payload


def test_extend_mp4_walks_moov_and_stops(tmp_path: Path):
    ftyp = _box(b"ftyp", b"isom" + b"\x00" * 4)
    moov = _box(b"moov", b"\x00" * 8)
    mdat = _box(b"mdat", b"Z" * 16)
    data = ftyp + moov + mdat
    out = _extend_mp4(data, 0, len(ftyp))
    # stops after including moov
    assert out.startswith(ftyp)
    assert moov in out
    assert out == data[: len(ftyp) + len(moov)]


def test_extend_mp4_no_structure_falls_back_to_scan(tmp_path: Path):
    ftyp = _box(b"ftyp", b"isom" + b"\x00" * 4)
    # after ftyp: garbage size that fails walk, then a moov further down
    garbage = b"\xff" * 16
    moov = _box(b"moov", b"\x00" * 4)
    data = ftyp + garbage + moov
    out = _extend_mp4(data, 0, len(ftyp))
    assert out.startswith(ftyp)
    assert moov in out


def test_extend_mp4_no_markers_caps_at_4096():
    ftyp = _box(b"ftyp", b"isom" + b"\x00" * 4)
    tail = b"Q" * 10000
    data = ftyp + tail
    out = _extend_mp4(data, 0, len(ftyp))
    assert len(out) <= len(ftyp) + 4096
    assert out.startswith(ftyp)


def test_extend_mp4_breaks_on_oversized_box():
    ftyp = _box(b"ftyp", b"isom" + b"\x00" * 4)
    bad = struct.pack(">I", 0xFFFFFF00) + b"mdat" + b"\x00" * 8
    data = ftyp + bad
    out = _extend_mp4(data, 0, len(ftyp))
    # walk stops; scan cannot honor oversized mdat size → 4096-byte cap
    assert out.startswith(ftyp)
    assert len(out) <= len(ftyp) + 4096
    assert len(out) <= len(data)


def test_extract_mp4_blobs_requires_size_before_ftyp():
    # ftyp at offset < 4 cannot be a valid top-level box start
    data = b"ftyp" + b"isom" + b"\x00" * 4
    assert _extract_mp4_blobs(data) == []


def test_extract_mp4_blobs_skips_out_of_range_size():
    # size claims more than available
    data = b"XXXX" + b"ftyp" + b"isom\x00\x00\x00\x00"
    assert _extract_mp4_blobs(data) == []


def test_extract_mp4_blobs_collects_valid_box():
    ftyp = _box(b"ftyp", b"isom" + b"\x00" * 4)
    data = b"PKGM0014" + b"\x00" * 8 + ftyp + b"\x00" * 8
    blobs = _extract_mp4_blobs(data)
    assert len(blobs) == 1
    assert blobs[0].startswith(ftyp[:8])


def test_dedup_prefers_longer_and_drops_contained():
    short = b"hello-world"
    long = b"prefix" + short + b"suffix"
    out = _dedup([short, long, short, long])
    assert out == [long]


def test_dedup_empty_and_unique():
    assert _dedup([]) == []
    assert _dedup([b"aa", b"bb"]) == [b"aa", b"bb"]


def test_unique_list_drops_duplicates(tmp_path: Path):
    a = tmp_path / "a.bin"
    a.write_bytes(b"x")
    b = tmp_path / "b.bin"
    b.write_bytes(b"y")
    missing = tmp_path / "gone.bin"
    out = _unique_list([a, a, b, missing, missing])
    assert out == [a, b, missing]


def test_is_mpkg_magic_and_generic_pkgm():
    assert is_mpkg(b"PKGM0014" + b"\x00" * 8)
    assert is_mpkg(b"\x00" * 10 + b"PKGM0019")
    assert is_mpkg(b"PKGM" + b"\x00" * 20)
    assert not is_mpkg(b"PKGV0005" + b"\x00" * 8)


def test_extract_mpkg_cancel_after_index_before_carve(tmp_path: Path, monkeypatch):
    import threading


    src = tmp_path / "c.mpkg"
    # large enough to pass size check; structured parse fails (WePkgError)
    src.write_bytes(b"PKGM0014" + b"\x11" * 64)
    ev = threading.Event()
    ev.set()
    with __import__("pytest").raises(WeMpkgError, match="已取消"):
        extract_mpkg(src, tmp_path / "out", cancel_event=ev)


def test_extract_mpkg_post_process_keeps_non_tex(tmp_path: Path):
    from core.we_mpkg import _post_process

    keep = tmp_path / "plain.txt"
    keep.write_bytes(b"hi")
    assert _post_process([keep], tmp_path) == [keep]


def test_extract_mpkg_carve_includes_png_via_iend(tmp_path: Path):
    # PNG without going through extract_embedded preference (mp4 empty)
    png = b"\x89PNG\r\n\x1a\n" + b"IHDR" + b"\x00" * 13 + b"IEND" + b"\x00\x00\x00\x00"
    data = b"PKGM0014" + b"\x00" * 32 + png + b"\x00" * 8
    src = tmp_path / "png.mpkg"
    src.write_bytes(data)
    outs = extract_mpkg(src, tmp_path / "out")
    assert any(p.suffix == ".png" for p in outs)


def test_extract_mpkg_cancel_during_carve_write(tmp_path: Path):
    import threading

    from core import we_mpkg as mod

    png = b"\x89PNG\r\n\x1a\n" + b"IEND" + b"\x00\x00\x00\x00"
    # two PNGs so second iteration can observe cancel
    data = b"PKGM0014" + b"\x00" * 32 + png + b"\x00" * 4 + png
    src = tmp_path / "twice.mpkg"
    src.write_bytes(data)
    ev = threading.Event()

    # force carved non-empty then cancel mid-write loop
    real_carve = mod._carve_media

    def carve_then_cancel(d: bytes):
        blobs = real_carve(d)
        ev.set()
        return blobs

    out_dir = tmp_path / "out"
    with __import__("pytest").raises(WeMpkgError, match="已取消"):
        # patch inside extract_mpkg call scope via monkeypatching module attr
        original = mod._carve_media
        mod._carve_media = carve_then_cancel
        try:
            extract_mpkg(src, out_dir, cancel_event=ev)
        finally:
            mod._carve_media = original
