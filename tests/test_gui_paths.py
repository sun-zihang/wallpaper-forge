from pathlib import Path

from core.tasks import OutputMode
from gui.pages.rewatermark_page import _clean_out
from gui.pages.unpack_page import _out_dir_for


def test_out_dir_for_overwrite_reuses_nonempty(tmp_path: Path):
    src = tmp_path / "scene.pkg"
    src.write_bytes(b"x")
    d = _out_dir_for(src, OutputMode.BESIDE, None, overwrite=False)
    d.mkdir(parents=True, exist_ok=True)
    (d / "old.bin").write_bytes(b"1")
    d2 = _out_dir_for(src, OutputMode.BESIDE, None, overwrite=True)
    assert d2 == d
    d3 = _out_dir_for(src, OutputMode.BESIDE, None, overwrite=False)
    assert d3.name.endswith("(1)")


def _two_same_stem(tmp_path: Path) -> tuple[Path, Path]:
    a = tmp_path / "w1" / "scene.tex"
    b = tmp_path / "w2" / "scene.tex"
    a.parent.mkdir(parents=True)
    b.parent.mkdir(parents=True)
    a.write_bytes(b"1")
    b.write_bytes(b"2")
    return a, b


def test_out_dir_for_batch_same_stem_dedupe_overwrite(tmp_path: Path):
    # finding 1: batch-level taken forces " (1)" on the 2nd same-stem source
    # even when overwrite=True (unified mode regression)
    a, b = _two_same_stem(tmp_path)
    unified = tmp_path / "unified"
    taken: set[Path] = set()
    d1 = _out_dir_for(a, OutputMode.UNIFIED, unified, overwrite=True, taken=taken)
    d2 = _out_dir_for(b, OutputMode.UNIFIED, unified, overwrite=True, taken=taken)
    assert d1 == unified / "scene"
    assert d2 == unified / "scene (1)"
    assert d1 != d2


def test_out_dir_for_batch_same_stem_dedupe_no_overwrite(tmp_path: Path):
    a, b = _two_same_stem(tmp_path)
    unified = tmp_path / "unified"
    taken: set[Path] = set()
    d1 = _out_dir_for(a, OutputMode.UNIFIED, unified, overwrite=False, taken=taken)
    d2 = _out_dir_for(b, OutputMode.UNIFIED, unified, overwrite=False, taken=taken)
    assert d1 == unified / "scene"
    assert d2 == unified / "scene (1)"


def test_out_dir_for_batch_dedupe_keeps_prior_run_reuse(tmp_path: Path):
    # overwrite=True still reuses an existing non-empty dir from a prior run
    # for the first batch entry; only the in-batch collision gets " (n)"
    a, b = _two_same_stem(tmp_path)
    unified = tmp_path / "unified"
    prior = unified / "scene"
    prior.mkdir(parents=True)
    (prior / "old.png").write_bytes(b"old")
    taken: set[Path] = set()
    d1 = _out_dir_for(a, OutputMode.UNIFIED, unified, overwrite=True, taken=taken)
    d2 = _out_dir_for(b, OutputMode.UNIFIED, unified, overwrite=True, taken=taken)
    assert d1 == prior
    assert d2 == unified / "scene (1)"


def test_clean_out_overwrite_keeps_existing(tmp_path: Path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    out = _clean_out(src, "png", OutputMode.UNIFIED, tmp_path, overwrite=False)
    out.write_bytes(b"old")
    out2 = _clean_out(src, "png", OutputMode.UNIFIED, tmp_path, overwrite=True)
    assert out2 == out
