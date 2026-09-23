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
