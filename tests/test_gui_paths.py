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


def test_clean_out_overwrite_keeps_existing(tmp_path: Path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    out = _clean_out(src, "png", OutputMode.UNIFIED, tmp_path, overwrite=False)
    out.write_bytes(b"old")
    out2 = _clean_out(src, "png", OutputMode.UNIFIED, tmp_path, overwrite=True)
    assert out2 == out
