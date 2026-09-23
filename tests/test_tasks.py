from pathlib import Path

from core.tasks import OutputMode, resolve_outputs


def test_beside_mode_creates_converted_subdir_path(tmp_path: Path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    outs = resolve_outputs([src], "jpg", OutputMode.BESIDE, None)
    assert outs == [tmp_path / "converted" / "a.jpg"]


def test_unified_mode_uses_dir(tmp_path: Path):
    src = tmp_path / "a.png"
    outdir = tmp_path / "out"
    outs = resolve_outputs([src], "png", OutputMode.UNIFIED, outdir)
    assert outs == [outdir / "a.png"]


def test_batch_name_collision_gets_suffix(tmp_path: Path):
    a = tmp_path / "a.png"
    b = tmp_path / "sub" / "a.png"
    b.parent.mkdir()
    a.write_bytes(b"1")
    b.write_bytes(b"2")
    outs = resolve_outputs([a, b], "jpg", OutputMode.UNIFIED, tmp_path / "out")
    assert outs[0].name == "a.jpg"
    assert outs[1].name == "a (1).jpg"


def test_never_points_at_source_file(tmp_path: Path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    outs = resolve_outputs([src], "png", OutputMode.UNIFIED, tmp_path)
    assert outs[0] != src
    assert outs[0].name == "a (1).png"
