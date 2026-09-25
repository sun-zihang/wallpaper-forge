from pathlib import Path

import pytest

from core.ffmpeg_finder import FFmpegNotFound, ffmpeg_available, find_ffmpeg


@pytest.fixture(autouse=True)
def _clear_ffmpeg_cache():
    find_ffmpeg.cache_clear()
    yield
    find_ffmpeg.cache_clear()


def test_env_var_wins(tmp_path: Path, monkeypatch):
    fake = tmp_path / "ffmpeg.exe"
    fake.write_bytes(b"")
    monkeypatch.setenv("WALLPAPER_FORGE_FFMPEG", str(fake))
    assert find_ffmpeg() == fake


def test_available_returns_bool():
    assert isinstance(ffmpeg_available(), bool)


def test_missing_raises_chinese(monkeypatch):
    monkeypatch.delenv("WALLPAPER_FORGE_FFMPEG", raising=False)
    monkeypatch.setattr("core.ffmpeg_finder.shutil.which", lambda *_: None)
    monkeypatch.setattr(
        "core.ffmpeg_finder._candidates",
        lambda: [Path("Z:/definitely-missing/ffmpeg.exe")],
    )
    try:
        find_ffmpeg()
        raise AssertionError("should raise")
    except FFmpegNotFound as e:
        assert "ffmpeg" in str(e)


def test_env_var_not_a_file_falls_through(tmp_path: Path, monkeypatch):
    from core import ffmpeg_finder as ff

    ghost = tmp_path / "ghost-ffmpeg"
    monkeypatch.setenv("WALLPAPER_FORGE_FFMPEG", str(ghost))
    real = Path(__file__).resolve()
    monkeypatch.setattr(ff, "_candidates", lambda: [ghost, real])
    assert find_ffmpeg() == real


def test_frozen_candidates_use_exe_dir(tmp_path: Path, monkeypatch):
    from core import ffmpeg_finder as ff

    exe = tmp_path / "WallpaperConverter.exe"
    exe.write_bytes(b"")
    (tmp_path / "_internal").mkdir()
    (tmp_path / "_internal" / "ffmpeg.exe").write_bytes(b"")
    monkeypatch.delenv("WALLPAPER_FORGE_FFMPEG", raising=False)
    monkeypatch.setattr(ff.shutil, "which", lambda *_: None)
    monkeypatch.setattr(ff.sys, "frozen", True, raising=False)
    monkeypatch.setattr(ff.sys, "executable", str(exe))
    found = ff._candidates()
    assert exe.parent / "ffmpeg.exe" in found
    assert exe.parent / "_internal" / "ffmpeg.exe" in found
    # sibling missing, bin missing, _internal present → _internal wins
    assert find_ffmpeg() == tmp_path / "_internal" / "ffmpeg.exe"


def test_candidates_include_path_which(tmp_path, monkeypatch):
    from core import ffmpeg_finder as ff

    fake = tmp_path / "which-ffmpeg"
    monkeypatch.setattr(ff.shutil, "which", lambda name: str(fake))
    found = ff._candidates()
    assert fake in found


def test_available_false_when_no_candidate(monkeypatch):
    from core import ffmpeg_finder as ff

    find_ffmpeg.cache_clear()
    monkeypatch.setattr(ff, "_candidates", lambda: [])
    assert ffmpeg_available() is False
