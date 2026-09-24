"""Update dialog / worker must thread the release asset SHA256 digest through."""

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
