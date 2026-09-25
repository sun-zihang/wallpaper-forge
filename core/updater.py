from __future__ import annotations

import contextlib
import hashlib
import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO = "sun-zihang/wallpaper-forge"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"

# Mirrors first, official last. Prefix must be substituted with the full
# https://github.com/... or https://api.github.com/... URL.
_URL_MIRRORS = [
    "https://ghproxy.net/{url}",
    "https://gh-proxy.com/{url}",
    "https://mirror.ghproxy.com/{url}",
    "https://ghfast.top/{url}",
    "{url}",
]

_ASSET_RE = re.compile(r"WallpaperConverter-Setup-.*\.exe$", re.I)
_UA = {"User-Agent": "WallpaperConverter-Updater", "Accept": "application/vnd.github+json"}


class UpdateError(Exception):
    pass


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    name: str
    download_url: str
    html_url: str
    expected_sha256: str | None = None


def parse_version(raw: str) -> tuple[int, ...]:
    text = (raw or "").strip().lstrip("vV")
    parts: list[int] = []
    for piece in re.split(r"[.\-+]", text):
        if piece.isdigit():
            parts.append(int(piece))
        else:
            m = re.match(r"(\d+)", piece)
            parts.append(int(m.group(1)) if m else 0)
    if not parts:
        raise UpdateError(f"无法解析版本号: {raw}")
    return tuple(parts)


def is_newer(remote: str, current: str) -> bool:
    return parse_version(remote) > parse_version(current)


def mirror_candidates(url: str) -> list[str]:
    return [tpl.format(url=url) for tpl in _URL_MIRRORS]


def setup_asset_url(tag: str) -> str:
    ver = tag.lstrip("vV")
    return f"https://github.com/{REPO}/releases/download/{tag}/WallpaperConverter-Setup-{ver}.exe"


def manual_download_links(download_url: str) -> list[str]:
    """Mirror-first direct links for copy/paste into a browser."""
    return mirror_candidates(download_url)


def parse_latest_release(payload: str | dict) -> ReleaseInfo:
    data = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(data, dict):
        raise UpdateError("GitHub 返回了无效数据")
    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        raise UpdateError("GitHub 返回中缺少版本 tag")
    html_url = str(data.get("html_url") or f"https://github.com/{REPO}/releases/tag/{tag}")
    name = str(data.get("name") or tag)
    download_url = ""
    expected_sha256: str | None = None
    for asset in data.get("assets") or []:
        aname = str(asset.get("name") or "")
        if _ASSET_RE.search(aname):
            download_url = str(asset.get("browser_download_url") or "")
            digest = str(asset.get("digest") or "").strip()
            if digest.lower().startswith("sha256:"):
                expected_sha256 = digest.split(":", 1)[1].strip().lower() or None
            break
    if not download_url:
        # fall back to standard URL pattern
        download_url = (
            f"https://github.com/{REPO}/releases/download/{tag}/"
            f"WallpaperConverter-Setup-{tag.lstrip('vV')}.exe"
        )
    return ReleaseInfo(
        tag=tag,
        name=name,
        download_url=download_url,
        html_url=html_url,
        expected_sha256=expected_sha256,
    )


def _http_get(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_latest_release(timeout: float = 12.0) -> ReleaseInfo:
    last_err: Exception | None = None
    for url in mirror_candidates(API_URL):
        try:
            body = _http_get(url, timeout=timeout)
            return parse_latest_release(body.decode("utf-8", errors="replace"))
        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            UpdateError,
            json.JSONDecodeError,
        ) as e:
            last_err = e
            continue
    raise UpdateError(f"无法获取最新版本信息：{last_err}")


def sha256_file(path: Path, *, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def download_update(
    asset_url: str,
    dest: Path,
    *,
    progress_cb: Callable[[int, int], None] | None = None,
    cancel_event=None,
    timeout: float = 30.0,
    chunk: int = 256 * 1024,
    expected_sha256: str | None = None,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_err: Exception | None = None
    for url in mirror_candidates(asset_url):
        try:
            return _download_one(
                url, dest, progress_cb, cancel_event, timeout, chunk, expected_sha256
            )
        except UpdateError as e:
            if "已取消" in str(e):
                raise
            last_err = e
            continue
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            continue
    raise UpdateError(f"下载更新失败：{last_err}")


def _download_one(
    url: str,
    dest: Path,
    progress_cb,
    cancel_event,
    timeout: float,
    chunk: int,
    expected_sha256: str | None = None,
) -> Path:
    req = urllib.request.Request(url, headers=_UA)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise UpdateError(f"HTTP {e.code}") from e
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with resp:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            last_pct = -1
            with open(tmp, "wb") as f:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        raise UpdateError("已取消")
                    block = resp.read(chunk)
                    if not block:
                        break
                    f.write(block)
                    done += len(block)
                    if progress_cb and total > 0:
                        pct = int(done * 100 / total)
                        if pct != last_pct:
                            last_pct = pct
                            progress_cb(done, total)
                    elif progress_cb:
                        progress_cb(done, total)
        if total and tmp.stat().st_size < total // 2:
            raise UpdateError("下载不完整")
        if expected_sha256:
            actual = sha256_file(tmp)
            if actual != expected_sha256.lower():
                raise UpdateError("安装包 SHA256 校验失败，可能是下载损坏或被篡改")
        tmp.replace(dest)
        if progress_cb and total:
            progress_cb(total, total)
        return dest
    finally:
        if tmp.exists() and not dest.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()
