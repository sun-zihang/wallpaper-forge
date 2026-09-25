from __future__ import annotations

from pathlib import Path

from core.space import _fmt, free_space_warning


def test_fmt_unit_boundaries():
    assert _fmt(0) == "0 B"
    assert _fmt(1023) == "1023 B"
    assert _fmt(1024) == "1024 B"
    assert _fmt(1024 * 1024 - 1) == "1048575 B"
    assert _fmt(1024 * 1024) == "1 MB"
    assert _fmt(1024 * 1024 * 1024 - 1) == "1024 MB"
    assert _fmt(1024 * 1024 * 1024) == "1.0 GB"
    assert _fmt(1024**4) == "1.0 TB"
    assert _fmt(1024**4 * 3) == "3.0 TB"


def test_no_sources_returns_none(tmp_path: Path):
    assert free_space_warning([]) is None


def test_plenty_of_space_returns_none(tmp_path: Path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x" * 1024)
    assert free_space_warning([src], [tmp_path / "out" / "a.jpg"]) is None


def test_missing_output_dir_probes_existing_parent(tmp_path: Path, monkeypatch):
    src = tmp_path / "a.png"
    src.write_bytes(b"x" * 4096)
    nested = tmp_path / "does" / "not" / "exist" / "a.jpg"
    monkeypatch.setattr(
        "core.space.shutil.disk_usage",
        lambda p: type("du", (), {"free": 100})(),
    )
    warn = free_space_warning([src], [nested])
    assert warn is not None
    assert "不足" in warn
    assert "100 B" in warn
    assert "4096 B" in warn


def test_low_space_warns_with_sizes(tmp_path: Path, monkeypatch):
    src = tmp_path / "a.png"
    src.write_bytes(b"x" * (2 * 1024 * 1024))
    monkeypatch.setattr(
        "core.space.shutil.disk_usage",
        lambda p: type("du", (), {"free": 1024 * 1024})(),
    )
    warn = free_space_warning([src], [tmp_path / "a.jpg"])
    assert warn is not None
    assert "1 MB" in warn
    assert "2 MB" in warn


def test_disk_usage_error_is_silent(tmp_path: Path, monkeypatch):
    src = tmp_path / "a.png"
    src.write_bytes(b"x" * 100)

    def boom(_p):
        raise OSError("nope")

    monkeypatch.setattr("core.space.shutil.disk_usage", boom)
    assert free_space_warning([src], [tmp_path / "a.jpg"]) is None


def test_unreadable_source_is_skipped(tmp_path: Path):
    missing = tmp_path / "gone.png"
    assert free_space_warning([missing], [tmp_path / "a.jpg"]) is None


def test_all_zero_sizes_returns_none(tmp_path: Path):
    src = tmp_path / "a.png"
    src.write_bytes(b"")
    assert free_space_warning([src], [tmp_path / "out" / "a.jpg"]) is None


def test_output_ancestor_is_file_falls_back_to_source_parent(tmp_path: Path, monkeypatch):
    src = tmp_path / "a.png"
    src.write_bytes(b"x" * 2048)
    blocker = tmp_path / "out"
    blocker.write_bytes(b"file")
    monkeypatch.setattr(
        "core.space.shutil.disk_usage",
        lambda p: type("du", (), {"free": 100})(),
    )
    warn = free_space_warning([src], [blocker / "a.jpg"])
    assert warn is not None
    assert "100 B" in warn
    assert "2048 B" in warn


def test_existing_ancestor_returns_existing_dir_or_file(tmp_path: Path):
    from core.space import _existing_ancestor

    real = _existing_ancestor(tmp_path / "a.png")
    assert real == tmp_path

    # existing file is a valid probe target (caller treats it as non-dir)
    f = tmp_path / "blocker"
    f.write_bytes(b"x")
    assert _existing_ancestor(f / "child" / "a.jpg") == f

    # missing leaf under an existing dir still walks up
    assert _existing_ancestor(tmp_path / "no" / "such" / "a.jpg") == tmp_path
