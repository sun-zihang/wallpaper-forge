from pathlib import Path

from core.tasks import (
    OutputMode,
    resolve_out_dir,
    resolve_outputs,
    would_overwrite_sources,
)


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


def test_resolve_outputs_unified_requires_dir(tmp_path: Path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    try:
        resolve_outputs([src], "jpg", OutputMode.UNIFIED, None)
        raise AssertionError("should raise")
    except ValueError as exc:
        assert "unified_dir" in str(exc)


def test_resolve_out_dir_unified_requires_dir(tmp_path: Path):
    src = tmp_path / "anim.gif"
    try:
        resolve_out_dir(src, OutputMode.UNIFIED, None)
        raise AssertionError("should raise")
    except ValueError as exc:
        assert "unified_dir" in str(exc)


def test_resolve_outputs_strips_dot_and_lowercases_ext(tmp_path: Path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    outs = resolve_outputs([src], ".JPG", OutputMode.BESIDE, None)
    assert outs == [tmp_path / "converted" / "a.jpg"]


def test_resolve_out_dir_overwrite_conflicts_with_file_same_name(tmp_path: Path):
    src = tmp_path / "anim.gif"
    d = resolve_out_dir(src, OutputMode.BESIDE, None, name_suffix="_frames")
    d.parent.mkdir(parents=True, exist_ok=True)
    d.write_bytes(b"not-a-dir")
    d2 = resolve_out_dir(
        src, OutputMode.BESIDE, None, name_suffix="_frames", overwrite=True
    )
    assert d2.name == "anim_frames (1)"


def test_would_overwrite_sources_pairs(tmp_path: Path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    other = tmp_path / "converted" / "b.jpg"
    pairs = would_overwrite_sources([src, tmp_path / "b.png"], [src, other])
    assert pairs == [(src, src)]


def test_resolve_out_dir_beside_basic(tmp_path: Path):
    src = tmp_path / "anim.gif"
    d = resolve_out_dir(src, OutputMode.BESIDE, None)
    assert d == tmp_path / "converted" / "anim"


def test_resolve_out_dir_name_suffix(tmp_path: Path):
    src = tmp_path / "anim.gif"
    d = resolve_out_dir(src, OutputMode.BESIDE, None, name_suffix="_frames")
    assert d == tmp_path / "converted" / "anim_frames"


def test_resolve_out_dir_unified_suffix(tmp_path: Path):
    src = tmp_path / "anim.gif"
    out = tmp_path / "unified"
    d = resolve_out_dir(src, OutputMode.UNIFIED, out, name_suffix="_frames")
    assert d == out / "anim_frames"


def test_resolve_out_dir_numbers_nonempty_existing(tmp_path: Path):
    src = tmp_path / "anim.gif"
    d = resolve_out_dir(src, OutputMode.BESIDE, None, name_suffix="_frames")
    d.mkdir(parents=True)
    (d / "frame_0001.png").write_bytes(b"x")
    d2 = resolve_out_dir(src, OutputMode.BESIDE, None, name_suffix="_frames")
    assert d2.name == "anim_frames (1)"


def test_resolve_out_dir_reuses_empty_dir(tmp_path: Path):
    src = tmp_path / "anim.gif"
    d = resolve_out_dir(src, OutputMode.BESIDE, None, name_suffix="_frames")
    d.mkdir(parents=True)  # empty (e.g. interrupted prior run)
    d2 = resolve_out_dir(src, OutputMode.BESIDE, None, name_suffix="_frames")
    assert d2 == d


def test_resolve_out_dir_overwrite_reuses_nonempty(tmp_path: Path):
    src = tmp_path / "anim.gif"
    d = resolve_out_dir(src, OutputMode.BESIDE, None, name_suffix="_frames")
    d.mkdir(parents=True)
    (d / "frame_0001.png").write_bytes(b"x")
    d2 = resolve_out_dir(
        src, OutputMode.BESIDE, None, name_suffix="_frames", overwrite=True
    )
    assert d2 == d


def test_would_overwrite_sources_empty_when_no_overlap(tmp_path: Path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    other = tmp_path / "b.png"
    other.write_bytes(b"y")
    assert would_overwrite_sources([src], [other]) == []


def test_resolve_out_dir_taken_dedupe_same_stem(tmp_path: Path):
    a = tmp_path / "w1" / "scene.pkg"
    b = tmp_path / "w2" / "scene.pkg"
    a.parent.mkdir()
    b.parent.mkdir()
    unified = tmp_path / "unified"
    taken: set[Path] = set()
    d1 = resolve_out_dir(a, OutputMode.UNIFIED, unified, overwrite=True, taken=taken)
    d2 = resolve_out_dir(b, OutputMode.UNIFIED, unified, overwrite=True, taken=taken)
    assert d1 == unified / "scene"
    assert d2 == unified / "scene (1)"
