from __future__ import annotations

from pathlib import Path

from core.space import free_space_warning


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
