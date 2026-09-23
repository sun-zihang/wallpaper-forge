from pathlib import Path

from core.tasks import OutputMode, resolve_outputs, would_overwrite_sources


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


def test_overwrite_allows_same_path_as_source(tmp_path: Path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    outs = resolve_outputs(
        [src], "png", OutputMode.UNIFIED, tmp_path, overwrite=True
    )
    assert outs == [src]


def test_overwrite_keeps_existing_output_path(tmp_path: Path):
    src = tmp_path / "a.png"
    outdir = tmp_path / "out"
    outdir.mkdir()
    (outdir / "a.jpg").write_bytes(b"old")
    src.write_bytes(b"x")
    outs = resolve_outputs(
        [src], "jpg", OutputMode.UNIFIED, outdir, overwrite=True
    )
    assert outs == [outdir / "a.jpg"]


def test_overwrite_still_dedupes_within_batch(tmp_path: Path):
    a = tmp_path / "a.png"
    b = tmp_path / "sub" / "a.png"
    b.parent.mkdir()
    a.write_bytes(b"1")
    b.write_bytes(b"2")
    outs = resolve_outputs(
        [a, b], "jpg", OutputMode.UNIFIED, tmp_path / "out", overwrite=True
    )
    assert outs[0].name == "a.jpg"
    assert outs[1].name == "a (1).jpg"


def test_would_overwrite_sources_pairs(tmp_path: Path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    other = tmp_path / "converted" / "b.jpg"
    pairs = would_overwrite_sources([src, tmp_path / "b.png"], [src, other])
    assert pairs == [(src, src)]
