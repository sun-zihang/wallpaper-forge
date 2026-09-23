from pathlib import Path

from PIL import Image

from core.annotate import crop_image
from core.image_ops import convert_image
from core.safeio import cleanup_part, needs_part, part_path, replace_part, staged_dst


def test_part_path_appends_part(tmp_path: Path):
    assert part_path(tmp_path / "a.png") == tmp_path / "a.png.part"


def test_needs_part_same_and_different(tmp_path: Path):
    a = tmp_path / "a.png"
    a.write_bytes(b"x")
    b = tmp_path / "b.png"
    assert needs_part(a, a) is True
    assert needs_part(a, b) is False


def test_staged_dst_same_path_replaces(tmp_path: Path):
    src = tmp_path / "a.txt"
    src.write_bytes(b"old")
    with staged_dst(src, src) as target:
        assert target == part_path(src)
        target.write_bytes(b"new")
    assert src.read_bytes() == b"new"
    assert not part_path(src).exists()


def test_staged_dst_same_path_error_cleans_part(tmp_path: Path):
    src = tmp_path / "a.txt"
    src.write_bytes(b"old")
    try:
        with staged_dst(src, src) as target:
            target.write_bytes(b"half")
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert src.read_bytes() == b"old"
    assert not part_path(src).exists()


def test_staged_dst_different_path_direct(tmp_path: Path):
    src = tmp_path / "a.txt"
    dst = tmp_path / "b.txt"
    with staged_dst(src, dst) as target:
        assert target == dst
        target.write_bytes(b"x")
    assert dst.read_bytes() == b"x"


def test_convert_image_inplace(tmp_path: Path):
    src = tmp_path / "img.png"
    Image.new("RGB", (64, 48), (1, 2, 3)).save(src)
    out = convert_image(src, src, max_width=32)
    assert out == src
    assert Image.open(src).size == (32, 24)
    assert not part_path(src).exists()


def test_crop_inplace(tmp_path: Path):
    src = tmp_path / "img.png"
    Image.new("RGB", (64, 48), (9, 9, 9)).save(src)
    out = crop_image(src, src, (0, 0, 32, 24))
    assert out == src
    assert Image.open(src).size == (32, 24)
