import hashlib
import json
import urllib.error
from typing import ClassVar

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


def test_parse_latest_release_empty_sha256_digest_becomes_none():
    payload = {
        "tag_name": "v1.0.0",
        "assets": [
            {
                "name": "WallpaperConverter-Setup-1.0.0.exe",
                "browser_download_url": "https://example.com/x.exe",
                "digest": "sha256:",
            },
        ],
    }
    info = parse_latest_release(payload)
    assert info.expected_sha256 is None


def test_parse_latest_release_accepts_json_string():
    info = parse_latest_release(json.dumps({"tag_name": "v1.0.0", "assets": []}))
    assert info.tag == "v1.0.0"
    assert "WallpaperConverter-Setup-1.0.0.exe" in info.download_url


def test_parse_latest_release_rejects_non_dict_payload():
    with pytest.raises(UpdateError, match="无效数据"):
        parse_latest_release("[1, 2, 3]")


def test_parse_latest_release_missing_assets_key_falls_back_to_pattern_url():
    info = parse_latest_release({"tag_name": "v2.0.0"})
    assert info.download_url.endswith("WallpaperConverter-Setup-2.0.0.exe")
    assert info.expected_sha256 is None


def test_sha256_file(tmp_path):
    p = tmp_path / "blob.bin"
    p.write_bytes(b"wallpaper")
    assert sha256_file(p) == hashlib.sha256(b"wallpaper").hexdigest()


def test_sha256_file_small_chunk_reads_every_block(tmp_path):
    p = tmp_path / "blob.bin"
    p.write_bytes(b"wallpaper-forge")
    assert sha256_file(p, chunk=1) == hashlib.sha256(b"wallpaper-forge").hexdigest()
    assert sha256_file(p, chunk=3) == hashlib.sha256(b"wallpaper-forge").hexdigest()


def test_download_update_rejects_bad_sha256(tmp_path, monkeypatch):
    from core import updater

    payload = b"not-the-real-installer"
    good = hashlib.sha256(payload).hexdigest()
    bad = "0" * 64

    def fake_urlopen(req, timeout=None):
        class _Resp:
            headers: ClassVar[dict[str, str]] = {"Content-Length": str(len(payload))}

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
        updater.download_update("https://example.com/x.exe", dest, expected_sha256=bad)
    assert not dest.exists()
    assert not dest.with_suffix(dest.suffix + ".part").exists()

    got = updater.download_update("https://example.com/x.exe", dest, expected_sha256=good)
    assert got.read_bytes() == payload


def test_parse_latest_release_missing_tag():
    with pytest.raises(UpdateError):
        parse_latest_release({"tag_name": ""})


def test_parse_latest_release_fallback_url():
    info = parse_latest_release({"tag_name": "v0.1.0", "assets": []})
    assert "WallpaperConverter-Setup-0.1.0.exe" in info.download_url


def test_fetch_latest_release_success(monkeypatch):
    from core import updater

    payload = {"tag_name": "v9.9.9", "assets": []}
    monkeypatch.setattr(
        updater,
        "_http_get",
        lambda url, timeout: json.dumps(payload).encode("utf-8"),
    )
    info = updater.fetch_latest_release()
    assert info.tag == "v9.9.9"
    assert info.download_url.endswith("WallpaperConverter-Setup-9.9.9.exe")


def test_fetch_latest_release_all_mirrors_fail(monkeypatch):
    from core import updater

    def boom(url, timeout):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(updater, "_http_get", boom)
    with pytest.raises(UpdateError, match="无法获取最新版本信息"):
        updater.fetch_latest_release()


def test_fetch_latest_release_invalid_json_falls_through(monkeypatch):
    from core import updater

    monkeypatch.setattr(updater, "_http_get", lambda url, timeout: b"not-json{{")
    with pytest.raises(UpdateError, match="无法获取最新版本信息"):
        updater.fetch_latest_release()


def test_download_update_cancel_raises_without_mirror_retry(tmp_path, monkeypatch):
    import threading

    from core import updater

    cancel = threading.Event()
    cancel.set()
    attempts: list[str] = []

    def fake_urlopen(req, timeout=None):
        attempts.append(getattr(req, "full_url", str(req)))

        class _Resp:
            headers: ClassVar[dict[str, str]] = {"Content-Length": "10"}

            def read(self, n=-1):
                return b"x" * 10

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return _Resp()

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)
    dest = tmp_path / "setup.exe"
    with pytest.raises(UpdateError, match="已取消"):
        updater.download_update("https://example.com/x.exe", dest, cancel_event=cancel)
    assert len(attempts) == 1
    assert not dest.exists()


def test_download_update_incomplete_body_raises(tmp_path, monkeypatch):
    from core import updater

    def fake_urlopen(req, timeout=None):
        class _Resp:
            headers: ClassVar[dict[str, str]] = {"Content-Length": "100"}

            def read(self, n=-1):
                if getattr(self, "_done", False):
                    return b""
                self._done = True
                return b"short"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return _Resp()

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)
    dest = tmp_path / "setup.exe"
    with pytest.raises(UpdateError, match="下载更新失败"):
        updater.download_update("https://example.com/x.exe", dest)
    assert not dest.exists()


def test_download_update_http_error_falls_through_to_final_message(tmp_path, monkeypatch):
    from core import updater

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            url="https://example.com/x.exe",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)
    dest = tmp_path / "setup.exe"
    with pytest.raises(UpdateError, match="下载更新失败"):
        updater.download_update("https://example.com/x.exe", dest)
    assert not dest.exists()
    assert not dest.with_suffix(dest.suffix + ".part").exists()


def test_download_update_progress_cb_without_content_length(tmp_path, monkeypatch):
    from core import updater

    payload = b"abcdef"

    def fake_urlopen(req, timeout=None):
        class _Resp:
            headers: ClassVar[dict[str, str]] = {}

            def read(self, n=-1):
                if getattr(self, "_pos", 0) >= len(payload):
                    return b""
                pos = self._pos = getattr(self, "_pos", 0)
                chunk = payload[pos:] if n < 0 else payload[pos : pos + n]
                self._pos = pos + len(chunk)
                return chunk

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return _Resp()

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)
    calls: list[tuple[int, int]] = []
    dest = tmp_path / "setup.exe"
    got = updater.download_update(
        "https://example.com/x.exe",
        dest,
        progress_cb=lambda d, t: calls.append((d, t)),
    )
    assert got.read_bytes() == payload
    assert calls
    assert all(total == 0 for _, total in calls)


def test_http_get_builds_request_and_returns_body(monkeypatch):
    from core import updater

    seen: dict = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"payload"

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["timeout"] = timeout
        seen["ua"] = req.get_header("User-agent")
        return _Resp()

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)
    assert updater._http_get("https://example.invalid/api", 7.5) == b"payload"
    assert seen["url"] == "https://example.invalid/api"
    assert seen["timeout"] == 7.5
    assert seen["ua"] == "WallpaperConverter-Updater"


def test_download_update_network_error_exhausts_mirrors(tmp_path, monkeypatch):
    from core import updater

    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("connection reset")

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)
    dest = tmp_path / "x.exe"
    with pytest.raises(UpdateError, match="下载更新失败"):
        updater.download_update("https://example.invalid/x.exe", dest)
    assert not dest.exists()


def test_download_update_progress_with_content_length(tmp_path, monkeypatch):
    from core import updater

    payload = b"z" * 100

    class _Resp:
        headers: ClassVar[dict[str, str]] = {"Content-Length": "100"}

        def __init__(self):
            self._pos = 0

        def read(self, n=-1):
            block = payload[self._pos : self._pos + n]
            self._pos += len(block)
            return block

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda req, timeout=None: _Resp())
    calls = []
    dest = tmp_path / "setup.exe"
    got = updater.download_update(
        "https://example.invalid/setup.exe",
        dest,
        progress_cb=lambda done, total: calls.append((done, total)),
        chunk=4,
    )
    assert got == dest
    assert dest.read_bytes() == payload
    assert calls
    assert calls[0][1] == 100
    assert calls[-1] == (100, 100)
