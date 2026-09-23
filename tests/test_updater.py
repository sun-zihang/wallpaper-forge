import pytest

from core.updater import (
    UpdateError,
    is_newer,
    mirror_candidates,
    parse_latest_release,
    parse_version,
)


def test_parse_version_basic():
    assert parse_version("v0.1.0") == (0, 1, 0)
    assert parse_version("1.2.3") == (1, 2, 3)
    assert parse_version("0.10") == (0, 10)


def test_is_newer():
    assert is_newer("0.2.0", "0.1.0")
    assert is_newer("v0.1.1", "0.1.0")
    assert not is_newer("0.1.0", "0.1.0")
    assert not is_newer("0.0.9", "0.1.0")
    assert is_newer("1.0.0", "0.9.9")


def test_mirror_candidates_order():
    url = "https://github.com/o/r/releases/download/v1/x.exe"
    c = mirror_candidates(url)
    assert len(c) >= 2
    assert c[-1] == url
    assert all(url in x or x == url for x in c)
    assert c[0] != url


def test_parse_latest_release_finds_setup_asset():
    payload = {
        "tag_name": "v0.2.0",
        "name": "v0.2.0",
        "html_url": "https://github.com/sun-zihang/wallpaper-forge/releases/tag/v0.2.0",
        "assets": [
            {"name": "source.zip", "browser_download_url": "https://example.com/source.zip"},
            {
                "name": "WallpaperConverter-Setup-0.2.0.exe",
                "browser_download_url": "https://github.com/sun-zihang/wallpaper-forge/releases/download/v0.2.0/WallpaperConverter-Setup-0.2.0.exe",
            },
        ],
    }
    info = parse_latest_release(payload)
    assert info.tag == "v0.2.0"
    assert info.download_url.endswith("WallpaperConverter-Setup-0.2.0.exe")


def test_parse_latest_release_missing_tag():
    with pytest.raises(UpdateError):
        parse_latest_release({"tag_name": ""})


def test_parse_latest_release_fallback_url():
    info = parse_latest_release({"tag_name": "v0.1.0", "assets": []})
    assert "WallpaperConverter-Setup-0.1.0.exe" in info.download_url
