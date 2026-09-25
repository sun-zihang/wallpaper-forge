"""Update dialog / worker must thread the release asset SHA256 digest through."""

import hashlib
from typing import ClassVar

from core.updater import ReleaseInfo


def _info(digest: str | None) -> ReleaseInfo:
    return ReleaseInfo(
        tag="v9.9.9",
        name="v9.9.9",
        download_url="https://github.com/o/r/releases/download/v9.9.9/WallpaperConverter-Setup-9.9.9.exe",
        html_url="https://github.com/o/r/releases/tag/v9.9.9",
        expected_sha256=digest,
    )


def test_dialog_label_mentions_sha256_verification(qapp):
    from PySide6.QtWidgets import QLabel

    from gui.update_dialog import UpdateDialog

    dialog = UpdateDialog(_info("0" * 64))
    try:
        labels = [lb.text() for lb in dialog.findChildren(QLabel)]
        assert any("SHA256" in t for t in labels), labels
    finally:
        dialog.close()
        dialog.deleteLater()
        qapp.processEvents()


def test_dialog_parent_version_matches_core(qapp):
    from core.version import __version__
    from gui.update_dialog import UpdateDialog

    dialog = UpdateDialog(_info(None))
    try:
        assert dialog.parent_version() == __version__
    finally:
        dialog.close()
        dialog.deleteLater()
        qapp.processEvents()


def test_dialog_on_progress_sets_percent_or_busy(qapp):
    from gui.update_dialog import UpdateDialog

    dialog = UpdateDialog(_info(None))
    try:
        dialog._on_progress(50, 100)
        assert dialog.bar.maximum() == 100
        assert dialog.bar.value() == 50

        dialog._on_progress(10, 0)
        assert dialog.bar.maximum() == 0  # busy indicator
    finally:
        dialog.close()
        dialog.deleteLater()
        qapp.processEvents()


def test_dialog_on_done_oserror_reenables_update_button(qapp, monkeypatch):
    from gui import update_dialog as mod

    errors = []
    monkeypatch.setattr(
        mod.QMessageBox,
        "critical",
        staticmethod(lambda *args: errors.append(args)),
    )
    monkeypatch.setattr(
        mod.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(OSError("no install"))
    )

    dialog = mod.UpdateDialog(_info(None))
    try:
        dialog.update_btn.setEnabled(True)
        dialog._on_done("C:\\missing-setup.exe")
        assert errors
        assert "无法启动安装程序" in errors[0][2]
        assert dialog.update_btn.isEnabled() is True
    finally:
        dialog.close()
        dialog.deleteLater()
        qapp.processEvents()


def test_dialog_passes_expected_sha256_to_download_worker(qapp, monkeypatch):
    from gui import update_dialog as mod

    captured = {}

    class FakeWorker:
        def __init__(self, url, dest, parent=None, *, expected_sha256=None):
            captured["url"] = url
            captured["dest"] = dest
            captured["expected_sha256"] = expected_sha256
            self.progressed = _Signal()
            self.finished_ok = _Signal()
            self.failed = _Signal()

        def start(self):
            captured["started"] = True

    class _Signal:
        def connect(self, *_a):
            pass

        def emit(self, *_a):
            pass

    monkeypatch.setattr(mod, "DownloadWorker", FakeWorker)
    digest = "a" * 64
    dialog = mod.UpdateDialog(_info(digest))
    try:
        dialog._start_update()
        assert captured["expected_sha256"] == digest
        assert captured["started"] is True
        assert captured["url"].endswith("WallpaperConverter-Setup-9.9.9.exe")
    finally:
        dialog.close()
        dialog.deleteLater()
        qapp.processEvents()


def test_download_worker_forwards_digest_to_download_update(monkeypatch, tmp_path):
    from gui import update_service as svc

    seen = {}

    def fake_download_update(url, dest, **kwargs):
        seen.update(kwargs)
        seen["url"] = url
        return dest

    monkeypatch.setattr("core.updater.download_update", fake_download_update)
    digest = "b" * 64
    worker = svc.DownloadWorker(
        "https://example.com/x.exe", tmp_path / "x.exe", expected_sha256=digest
    )
    worker.run()
    assert seen.get("expected_sha256") == digest
    assert seen.get("url") == "https://example.com/x.exe"


def test_dialog_failed_offers_mirror_links(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from gui.update_dialog import UpdateDialog

    captured = {}

    def fake_exec(self):
        captured["title"] = self.windowTitle()
        captured["text"] = self.text()
        captured["informative"] = self.informativeText()
        captured["detailed"] = self.detailedText()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    dialog = UpdateDialog(_info(None))
    try:
        dialog._on_failed("安装包 SHA256 校验失败")
        assert captured["title"] == "下载失败"
        assert "SHA256" in captured["text"]
        assert "ghproxy.net" in captured["informative"]
        assert "发布页" in captured["informative"]
        assert "https://ghproxy.net/" in captured["detailed"]
        assert dialog.update_btn.isEnabled() is True
        assert dialog.bar.isHidden() is True
    finally:
        dialog.close()
        dialog.deleteLater()
        qapp.processEvents()


def test_download_update_retries_next_mirror_after_sha256_fail(tmp_path, monkeypatch):
    from core import updater

    good = b"installer-bytes"
    good_hash = hashlib.sha256(good).hexdigest()
    attempts: list[str] = []
    # First mirror serves wrong bytes; second serves the real ones.
    bodies = [b"corrupted-bytes", good]

    def fake_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        attempts.append(url)
        payload = bodies[min(len(attempts) - 1, len(bodies) - 1)]

        class _Resp:
            headers: ClassVar[dict[str, str]] = {"Content-Length": str(len(payload))}
            _payload = payload
            _pos = 0

            def read(self, n=-1):
                if n < 0:
                    chunk = self._payload[self._pos :]
                    self._pos = len(self._payload)
                    return chunk
                chunk = self._payload[self._pos : self._pos + n]
                self._pos += len(chunk)
                return chunk

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return _Resp()

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)
    dest = tmp_path / "setup.exe"
    got = updater.download_update(
        "https://github.com/o/r/releases/download/v9/x.exe",
        dest,
        expected_sha256=good_hash,
    )
    assert len(attempts) >= 2, attempts
    assert got.read_bytes() == good
    assert not dest.with_suffix(dest.suffix + ".part").exists()
