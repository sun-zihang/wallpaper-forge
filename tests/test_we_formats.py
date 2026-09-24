from __future__ import annotations

import struct
from pathlib import Path

import pytest

from core.we_mpkg import WeMpkgError, extract_mpkg, is_mpkg
from core.we_pkg import WePkgError, extract_pkg, read_pkg_index
from core.we_tex import WeTexError, extract_embedded, extract_tex


def _build_pkg(files: dict[str, bytes], magic: bytes = b"PKGV0005") -> bytes:
    """Build a minimal PKG blob matching WE index layout."""
    header = magic
    # index first to compute offsets
    names = list(files.keys())
    # data block laid out in order
    blobs = [files[n] for n in names]
    # offsets relative to data block start — computed after we know index size
    # We assemble: u32 hlen | header | u32 count | entries | data
    # entry size depends on name bytes
    def entry_size(name: bytes) -> int:
        return 4 + len(name) + 8

    index_payload = b"".join(
        struct.pack("<I", len(n.encode())) + n.encode() + b"" for n in names
    )
    # placeholders for offsets — compute index length first
    count = len(names)
    # iterate to resolve offsets
    # index without offsets values unknown: size = sum(4+namelen+8)
    index_size = 4 + len(header)  # no - separate
    # actual layout size before data:
    # 4 + len(header) + 4 + sum(4+namelen+8)
    pre = 4 + len(header) + 4 + sum(4 + len(n.encode()) + 8 for n in names)
    offsets = []
    pos = 0
    for b in blobs:
        offsets.append(pos)
        pos += len(b)

    out = bytearray()
    out += struct.pack("<I", len(header))
    out += header
    out += struct.pack("<I", count)
    for n, off in zip(names, offsets):
        nb = n.encode()
        out += struct.pack("<I", len(nb))
        out += nb
        out += struct.pack("<I", off)
        out += struct.pack("<I", len(files[n]))
    assert len(out) == pre
    for b in blobs:
        out += b
    return bytes(out)


def test_read_pkg_index_roundtrip():
    pkg = _build_pkg({"a.txt": b"hello", "sub/b.bin": b"\x00\x01"})
    magic, entries = read_pkg_index(pkg)
    assert magic.startswith("PKGV")
    assert [e.name for e in entries] == ["a.txt", "sub/b.bin"]
    assert entries[0].length == 5


def test_read_pkg_index_zero_entries():
    pkg = _build_pkg({})
    magic, entries = read_pkg_index(pkg)
    assert entries == []


def test_read_pkg_index_normalizes_backslashes():
    pkg = _build_pkg({"sub\\nested\\a.txt": b"x"})
    _, entries = read_pkg_index(pkg)
    assert entries[0].name == "sub/nested/a.txt"


def test_read_pkg_index_rejects_oversized_header():
    # header_len larger than remaining payload
    data = struct.pack("<I", 0xFFFFFF) + b"XXXX"
    with pytest.raises(WePkgError, match="头部长度异常"):
        read_pkg_index(data)


def test_read_pkg_index_rejects_absurd_file_count():
    # valid-looking header, then count > 1_000_000
    header = b"PKGV0005"
    data = struct.pack("<I", len(header)) + header + struct.pack("<I", 2_000_000)
    with pytest.raises(WePkgError, match="文件数异常"):
        read_pkg_index(data)


def test_read_pkg_index_rejects_truncated_entry():
    header = b"PKGV0005"
    # count=1 but name_len extends past buffer
    data = struct.pack("<I", len(header)) + header + struct.pack("<I", 1) + struct.pack("<I", 100) + b"ab"
    with pytest.raises(WePkgError, match="索引损坏"):
        read_pkg_index(data)


def test_read_pkg_index_rejects_tiny_buffer():
    with pytest.raises(WePkgError, match="过小"):
        read_pkg_index(b"abc")


def test_extract_pkg_rejects_out_of_bounds_offset(tmp_path: Path):
    # valid index but entry.offset/length point past EOF
    header = b"PKGV0005"
    name = b"a.txt"
    out = bytearray()
    out += struct.pack("<I", len(header))
    out += header
    out += struct.pack("<I", 1)
    out += struct.pack("<I", len(name)) + name
    out += struct.pack("<I", 0x7FFF0000)  # absurd offset
    out += struct.pack("<I", 0x7FFF0000)  # absurd length
    src = tmp_path / "oob.pkg"
    src.write_bytes(bytes(out))
    with pytest.raises(WePkgError, match="条目越界"):
        extract_pkg(src, tmp_path / "out")


def test_extract_pkg_empty_index_writes_nothing(tmp_path: Path):
    pkg = _build_pkg({})
    src = tmp_path / "empty.pkg"
    src.write_bytes(pkg)
    out_dir = tmp_path / "out"
    outs = extract_pkg(src, out_dir)
    assert outs == []
    assert list(out_dir.iterdir()) == []


def test_extract_pkg(tmp_path: Path):
    pkg = _build_pkg({"a.txt": b"hello", "sub/b.bin": b"\x00\x01"})
    src = tmp_path / "scene.pkg"
    src.write_bytes(pkg)
    out = extract_pkg(src, tmp_path / "converted" / "scene")
    assert (tmp_path / "converted" / "scene" / "a.txt").read_bytes() == b"hello"
    assert (tmp_path / "converted" / "scene" / "sub" / "b.bin").exists()
    assert len(out) == 2


def test_extract_pkg_bad_header(tmp_path: Path):
    src = tmp_path / "bad.pkg"
    src.write_bytes(b"XXXX" + b"A" * 2000)
    with pytest.raises(WePkgError):
        extract_pkg(src, tmp_path / "out")


def test_extract_pkg_rejects_path_traversal(tmp_path: Path):
    pkg = _build_pkg({"../escape.txt": b"pwned"})
    src = tmp_path / "evil.pkg"
    src.write_bytes(pkg)
    out_dir = tmp_path / "converted" / "evil"
    with pytest.raises(WePkgError, match="非法路径"):
        extract_pkg(src, out_dir)
    assert not (tmp_path / "converted" / "escape.txt").exists()
    assert not (tmp_path / "escape.txt").exists()


def test_extract_pkg_strips_leading_slash_under_out_dir(tmp_path: Path):
    # Leading "/" is stripped so the entry lands inside out_dir, not at FS root.
    pkg = _build_pkg({"/abs-like.txt": b"x"})
    src = tmp_path / "abs.pkg"
    src.write_bytes(pkg)
    out_dir = tmp_path / "converted" / "abs"
    outs = extract_pkg(src, out_dir)
    assert len(outs) == 1
    assert outs[0] == out_dir / "abs-like.txt"
    assert outs[0].is_file()
    assert outs[0].read_bytes() == b"x"


def test_extract_pkg_rejects_drive_letter_path(tmp_path: Path):
    # On Windows pathlib joins an absolute right-hand path, so "C:/..." would
    # escape out_dir — the resolve()/relative_to guard must catch it.
    pkg = _build_pkg({"C:/Windows/evil.txt": b"pwned"})
    src = tmp_path / "drive.pkg"
    src.write_bytes(pkg)
    with pytest.raises(WePkgError, match="非法路径"):
        extract_pkg(src, tmp_path / "out")


def test_extract_pkg_progress_cb(tmp_path: Path):
    pkg = _build_pkg({"a.txt": b"a", "b.txt": b"b"})
    src = tmp_path / "p.pkg"
    src.write_bytes(pkg)
    seen: list[tuple[int, int]] = []
    extract_pkg(src, tmp_path / "out", progress_cb=lambda i, t: seen.append((i, t)))
    assert seen == [(1, 2), (2, 2)]


def test_extract_pkg_cancel_before_start(tmp_path: Path):
    import threading

    pkg = _build_pkg({"a.txt": b"a"})
    src = tmp_path / "c.pkg"
    src.write_bytes(pkg)
    ev = threading.Event()
    ev.set()
    out_dir = tmp_path / "out"
    with pytest.raises(WePkgError, match="已取消"):
        extract_pkg(src, out_dir, cancel_event=ev)
    assert not (out_dir / "a.txt").exists()


def test_extract_pkg_cancel_midway_leaves_no_escape(tmp_path: Path):
    # cancel after first entry is observed at the top of the next iteration
    import threading

    pkg = _build_pkg({"a.txt": b"a", "b.txt": b"b"})
    src = tmp_path / "c2.pkg"
    src.write_bytes(pkg)
    ev = threading.Event()
    out_dir = tmp_path / "out"

    def cancel_after_first(i: int, t: int) -> None:
        ev.set()

    with pytest.raises(WePkgError, match="已取消"):
        extract_pkg(src, out_dir, cancel_event=ev, progress_cb=cancel_after_first)
    # first file may exist; second must not
    assert not (out_dir / "b.txt").exists()


def test_extract_mpkg_path_traversal_does_not_escape(tmp_path: Path):
    # Structured extract raises WePkgError; mpkg falls through to carving.
    # A "../" entry must never land outside out_dir.
    pkg = _build_pkg({"../escape.txt": b"pwned"}, magic=b"PKGM0014")
    src = tmp_path / "evil.mpkg"
    src.write_bytes(pkg)
    out_dir = tmp_path / "converted" / "evil"
    try:
        outs = extract_mpkg(src, out_dir)
    except WeMpkgError:
        outs = []
    assert not (tmp_path / "converted" / "escape.txt").exists()
    assert not (tmp_path / "escape.txt").exists()
    for p in outs:
        assert out_dir.resolve() in p.resolve().parents or p.resolve() == out_dir.resolve()


def test_extract_tex_embedded_webp():
    # RIFF....WEBP payload with length prefix before the signature
    webp = (
        b"RIFF"
        + (12).to_bytes(4, "little")
        + b"WEBP"
        + b"VP8 "
        + (4).to_bytes(4, "little")
        + b"xxxx"
    )
    # ensure extract_embedded finds WEBP at a position where i>=8 for RIFF check
    blob = b"\x00" * 16 + struct.pack("<I", len(webp)) + webp + b"\x00" * 8
    ext, payload = extract_embedded(blob)
    assert ext == ".webp"
    assert payload.startswith(b"RIFF")


def test_extract_tex_embedded_jpeg():
    # SOI ... EOI with optional length prefix; extract trims at EOI
    # payload must be >= 16 bytes (extract_embedded rejects shorter)
    jpg = b"\xff\xd8\xff\xe0" + b"\x00\x10" + b"JFIF\x00" + b"\x00" * 8 + b"\xff\xd9"
    assert len(jpg) >= 16
    blob = b"\x00" * 8 + struct.pack("<I", len(jpg)) + jpg + b"\xbb" * 8
    ext, payload = extract_embedded(blob)
    assert ext == ".jpg"
    assert payload.startswith(b"\xff\xd8")
    assert payload.endswith(b"\xff\xd9")


def test_extract_mpkg_too_small():
    src = Path("x.mpkg")
    # write via tmp in test — use monkeypatch-free approach
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.mpkg"
        p.write_bytes(b"short")
        with pytest.raises(WeMpkgError, match="过小"):
            extract_mpkg(p, Path(td) / "out")


def test_tex_embedded_png():
    png = (
        b"\x89PNG\r\n\x1a\n"
        + b"IHDR" + b"\x00" * 13
        + b"IEND" + b"\x00" * 4
    )
    # length prefix
    blob = b"\x00" * 16 + struct.pack("<I", len(png)) + png + b"\x00" * 8
    ext, payload = extract_embedded(blob)
    assert ext == ".png"
    assert payload.startswith(b"\x89PNG")


def test_tex_embedded_mp4():
    ftyp = struct.pack(">I", 20) + b"ftyp" + b"isom" + b"\x00\x00\x00\x00" + b"isom"
    assert len(ftyp) == 20
    blob = b"\xaa" * 32 + ftyp + b"\xbb" * 16
    ext, payload = extract_embedded(blob)
    assert ext == ".mp4"
    assert b"ftyp" in payload
    assert payload.startswith(b"\x00\x00\x00\x14")


def test_extract_tex_writes_png(tmp_path: Path):
    png = b"\x89PNG\r\n\x1a\n" + b"IEND" + b"\x00" * 4
    src = tmp_path / "layer.tex"
    src.write_bytes(b"\x00" * 8 + struct.pack("<I", len(png)) + png)
    out = extract_tex(src, tmp_path / "layer")
    assert out.suffix == ".png"
    assert out.read_bytes().startswith(b"\x89PNG")


def test_extract_tex_fallback_raw(tmp_path: Path):
    src = tmp_path / "empty.tex"
    src.write_bytes(b"\x00" * 64)
    out = extract_tex(src, tmp_path / "empty")
    assert out.suffix == ".tex"
    assert out.read_bytes() == src.read_bytes()


def test_extract_tex_overwrite_replaces_same_name(tmp_path: Path):
    # 构造内嵌 PNG 的 .tex（与现有 embedded 测试同布局）
    png_sig = b"\x89PNG\r\n\x1a\n" + b"\x00" * 10
    import struct as _struct

    blob = b"\x00" * 16 + _struct.pack("<I", len(png_sig)) + png_sig + b"\x00" * 8
    src = tmp_path / "scene.tex"
    src.write_bytes(blob)
    first = extract_tex(src, tmp_path / "out" / "scene")
    assert first.exists()
    # 默认再抽 → 不覆盖，带 (1)
    second = extract_tex(src, tmp_path / "out" / "scene")
    assert second != first and second.exists()
    # overwrite → 仍写第一个路径
    third = extract_tex(src, tmp_path / "out" / "scene", overwrite=True)
    assert third == first


def test_mpkg_carves_mp4(tmp_path: Path):
    ftyp = struct.pack(">I", 32) + b"ftypmp42" + b"\x00\x00\x00\x00" + b"mp42mp41"
    moov = struct.pack(">I", 16) + b"moov" + b"\x00" * 8
    mdat = struct.pack(">I", 16) + b"mdat" + b"\x00" * 8
    # put ftyp+moov+mdat
    video = ftyp + moov + mdat
    data = b"PKGM0014" + b"\x00" * 64 + video + b"\x00" * 32
    src = tmp_path / "wall.mpkg"
    src.write_bytes(data)
    assert is_mpkg(data)
    outs = extract_mpkg(src, tmp_path / "converted" / "wall")
    assert outs
    assert any(p.suffix == ".mp4" for p in outs)


def test_mpkg_garbage_raises(tmp_path: Path):
    src = tmp_path / "x.mpkg"
    src.write_bytes(b"PKGM0019" + b"\x11" * 100)
    with pytest.raises(WeMpkgError):
        extract_mpkg(src, tmp_path / "out")


def test_mpkg_via_pkg_layout(tmp_path: Path):
    pkg = _build_pkg({"preview.png": b"\x89PNG\r\n\x1a\nIEND\x00\x00\x00\x00"}, magic=b"PKGM0014")
    src = tmp_path / "w.mpkg"
    src.write_bytes(pkg)
    outs = extract_mpkg(src, tmp_path / "converted" / "w")
    assert (tmp_path / "converted" / "w" / "preview.png").exists() or any(
        p.suffix == ".png" for p in outs
    )


def test_mpkg_post_process_overwrites_existing_extract(tmp_path: Path):
    # finding 2: _post_process must overwrite=True so a reused non-empty
    # out_dir gets same-name replacement, not "scene (1).png"
    png = b"\x89PNG\r\n\x1a\n" + b"IEND" + b"\x00" * 4
    tex = b"\x00" * 16 + struct.pack("<I", len(png)) + png + b"\x00" * 8
    pkg = _build_pkg({"scene.tex": tex}, magic=b"PKGM0014")
    src = tmp_path / "w.mpkg"
    src.write_bytes(pkg)
    out_dir = tmp_path / "converted" / "w"
    first = extract_mpkg(src, out_dir)
    assert any(p.name == "scene.png" for p in first)
    assert (out_dir / "scene.png").exists()
    second = extract_mpkg(src, out_dir)
    assert any(p.name == "scene.png" for p in second)
    assert (out_dir / "scene.png").exists()


def test_mpkg_drops_converted_tex_intermediate(tmp_path: Path):
    # after successful tex conversion the intermediate .tex must not linger
    png = b"\x89PNG\r\n\x1a\n" + b"IEND" + b"\x00" * 4
    tex = b"\x00" * 16 + struct.pack("<I", len(png)) + png + b"\x00" * 8
    pkg = _build_pkg({"scene.tex": tex}, magic=b"PKGM0014")
    src = tmp_path / "w.mpkg"
    src.write_bytes(pkg)
    out_dir = tmp_path / "converted" / "w"
    outs = extract_mpkg(src, out_dir)
    assert any(p.name == "scene.png" for p in outs)
    assert not (out_dir / "scene.tex").exists()
    assert all(p.suffix.lower() != ".tex" for p in outs)
    assert not (out_dir / "scene (1).png").exists()
