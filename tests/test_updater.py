import hashlib

import pytest

from core.updater import (
    UpdateError,
    is_newer,
    manual_download_links,
    mirror_candidates,
    parse_latest_release,
    parse_version,
    setup_asset_url,
    sha256_file,
)


def test_parse_version_basic():
    assert parse_version("v0.1.0") == (0, 1, 0)
    assert parse_version("1.2.3") == (1, 2, 3)
    assert parse_version("0.10") == (0, 10)


def test_parse_version_prerelease_and_build():
    assert parse_version("1.2.3-beta.1") == (1, 2, 3, 0, 1)
    assert parse_version("1.2.3+build5") == (1, 2, 3, 0)
    assert parse_version("1.2.3-rc1") == (1, 2, 3, 0)
    assert parse_version("v1.2") == (1, 2)


def test_parse_version_empty_or_garbage_returns_zero_tuple():
    # non-numeric pieces collapse to 0; only fully empty part list raises
    assert parse_version("") == (0,)
    assert parse_version("abc") == (0,)
    assert parse_version(None) == (0,)


def test_is_newer_prerelease_shorter_loses():
    # (1,2,3,0,1) vs (1,2,3) → longer wins when prefix equal
    assert is_newer("1.2.3-beta.1", "1.2.3")
    assert not is_newer("1.2.3", "1.2.3-beta.1")
    assert is_newer("0.6.4", "0.6.3")


def test_mirror_candidates_substitutes_full_url():
    url = "https://api.github.com/repos/o/r/releases/latest"
    for c in mirror_candidates(url):
        assert url in c or c == url
    assert any(c.startswith("https://ghproxy.net/") for c in mirror_candidates(url))


def test_setup_asset_url_strips_v_prefix():
    assert setup_asset_url("V1.0.0").endswith("WallpaperConverter-Setup-1.0.0.exe")
    assert setup_asset_url("1.0.0").endswith("/1.0.0/WallpaperConverter-Setup-1.0.0.exe")


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


def test_setup_asset_url():
    url = setup_asset_url("v0.4.0")
    assert url.endswith("WallpaperConverter-Setup-0.4.0.exe")
    assert "sun-zihang/wallpaper-forge" in url


def test_manual_download_links_mirror_first():
    url = setup_asset_url("v0.4.0")
    links = manual_download_links(url)
    assert links[0] != url
    assert links[-1] == url
    assert all(url in x or x == url for x in links)


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
    assert info.expected_sha256 is None


def test_parse_latest_release_reads_sha256_digest():
    payload = {
        "tag_name": "v0.6.3",
        "assets": [
            {
                "name": "WallpaperConverter-Setup-0.6.3.exe",
                "browser_download_url": "https://github.com/o/r/releases/download/v0.6.3/x.exe",
                "digest": "sha256:2FE66D5FF088D9D2B0135E51EAF2ACBD505D40DB23214226D3CC5CFDF9344B68",
            },
        ],
    }
    info = parse_latest_release(payload)
    assert info.expected_sha256 == (
        "2fe66d5ff088d9d2b0135e51eaf2acbd505d40db23214226d3cc5cfdf9344b68"
    )


def test_parse_latest_release_ignores_non_sha256_digest():
    payload = {
        "tag_name": "v0.6.3",
        "assets": [
            {
                "name": "WallpaperConverter-Setup-0.6.3.exe",
                "browser_download_url": "https://example.com/x.exe",
                "digest": "sha512:abc",
            },
        ],
    }
    info = parse_latest_release(payload)
    assert info.expected_sha256 is None


def test_sha256_file(tmp_path):
    p = tmp_path / "blob.bin"
    p.write_bytes(b"wallpaper")
    assert sha256_file(p) == hashlib.sha256(b"wallpaper").hexdigest()


def test_download_update_rejects_bad_sha256(tmp_path, monkeypatch):
    from core import updater

    payload = b"not-the-real-installer"
    good = hashlib.sha256(payload).hexdigest()
    bad = "0" * 64

    def fake_urlopen(req, timeout=None):
        class _Resp:
            headers = {"Content-Length": str(len(payload))}

            def read(self, n=-1):
                if getattr(self, "_done", False):
                    return b""
                self._done = True
                return payload if n < 0 else payload[:n]

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return _Resp()

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)
    dest = tmp_path / "WallpaperConverter-Setup-9.9.9.exe"

    with pytest.raises(UpdateError, match="校验失败"):
        updater.download_update(
            "https://example.com/x.exe", dest, expected_sha256=bad
        )
    assert not dest.exists()
    assert not dest.with_suffix(dest.suffix + ".part").exists()

    got = updater.download_update(
        "https://example.com/x.exe", dest, expected_sha256=good
    )
    assert got.read_bytes() == payload


def test_parse_latest_release_missing_tag():
    with pytest.raises(UpdateError):
        parse_latest_release({"tag_name": ""})


def test_parse_latest_release_fallback_url():
    info = parse_latest_release({"tag_name": "v0.1.0", "assets": []})
    assert "WallpaperConverter-Setup-0.1.0.exe" in info.download_url
