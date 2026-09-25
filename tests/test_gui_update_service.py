"""ReleaseCheckWorker / DownloadWorker / UpdateService pure-path coverage."""

from __future__ import annotations

from core.updater import ReleaseInfo, UpdateError


def _info(tag: str = "v9.9.9") -> ReleaseInfo:
    return ReleaseInfo(
        tag=tag,
        name=tag,
        download_url="https://example.com/x.exe",
        html_url="https://example.com/html",
    )


def test_release_check_worker_emits_info_when_remote_is_newer(monkeypatch):
    from gui import update_service as svc

    info = _info("v9.9.9")
    monkeypatch.setattr(svc, "fetch_latest_release", lambda *a, **k: info)
    worker = svc.ReleaseCheckWorker("0.6.3")
    got = []
    worker.finished_ok.connect(got.append)
    worker.run()
    assert got == [info]


def test_release_check_worker_emits_none_when_already_latest(monkeypatch):
    from gui import update_service as svc

    info = _info("v0.0.1")
    monkeypatch.setattr(svc, "fetch_latest_release", lambda *a, **k: info)
    worker = svc.ReleaseCheckWorker("9.9.9")
    got = []
    worker.finished_ok.connect(got.append)
    worker.run()
    assert got == [None]


def test_release_check_worker_forwards_update_error(monkeypatch):
    from gui import update_service as svc

    def boom(*a, **k):
        raise UpdateError("网络错误")

    monkeypatch.setattr(svc, "fetch_latest_release", boom)
    worker = svc.ReleaseCheckWorker("0.6.3")
    errs = []
    worker.failed.connect(errs.append)
    worker.run()
    assert errs == ["网络错误"]


def test_release_check_worker_wraps_unexpected_exception(monkeypatch):
    from gui import update_service as svc

    def boom(*a, **k):
        raise ValueError("bad")

    monkeypatch.setattr(svc, "fetch_latest_release", boom)
    worker = svc.ReleaseCheckWorker("0.6.3")
    errs = []
    worker.failed.connect(errs.append)
    worker.run()
    assert len(errs) == 1
    assert "检查更新失败" in errs[0]
    assert "bad" in errs[0]


def test_download_worker_forwards_update_error(monkeypatch, tmp_path):
    from gui import update_service as svc

    def boom(*a, **k):
        raise UpdateError("HTTP 404")

    monkeypatch.setattr("core.updater.download_update", boom)
    worker = svc.DownloadWorker("https://example.com/x.exe", tmp_path / "x.exe")
    fails = []
    worker.failed.connect(fails.append)
    worker.run()
    assert fails == ["HTTP 404"]


def test_download_worker_wraps_unexpected_exception(monkeypatch, tmp_path):
    from gui import update_service as svc

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr("core.updater.download_update", boom)
    worker = svc.DownloadWorker("https://example.com/x.exe", tmp_path / "x.exe")
    fails = []
    worker.failed.connect(fails.append)
    worker.run()
    assert len(fails) == 1
    assert "下载失败" in fails[0]
    assert "disk full" in fails[0]


def test_update_service_on_ok_routes_info_and_none(qapp):
    from gui.update_service import UpdateService

    svc = UpdateService("0.6.3")
    updates = []
    nones = []
    svc.update_available.connect(updates.append)
    svc.no_update.connect(lambda: nones.append(1))

    info = _info()
    svc._on_ok(info)
    assert updates == [info]
    assert nones == []

    svc._on_ok(None)
    assert nones == [1]
    assert len(updates) == 1


def test_update_service_check_async_skips_when_already_running(qapp):
    from gui import update_service as svc_mod

    started = []

    class FakeWorker:
        def __init__(self, *a, **k):
            pass

        def isRunning(self):
            return True

        def start(self):
            started.append(1)

        def finished_ok(self):  # pragma: no cover - never connected
            raise AssertionError("must not connect when skipping")

        class _Sig:
            def connect(self, *_a):
                raise AssertionError("must not connect when skipping")

        @property
        def failed(self):
            return FakeWorker._Sig()

    svc = svc_mod.UpdateService("0.6.3")
    svc._check = FakeWorker()
    svc.check_async()
    assert started == []


def test_download_worker_cancel_sets_event(tmp_path):
    from gui.update_service import DownloadWorker

    worker = DownloadWorker("https://example.com/x.exe", tmp_path / "x.exe")
    assert not worker._cancel.is_set()
    worker.cancel()
    assert worker._cancel.is_set()


def test_download_worker_emits_progress(monkeypatch, tmp_path):
    from gui import update_service as svc

    def fake_download_update(url, dest, *, progress_cb=None, **kwargs):
        progress_cb(50, 100)
        return dest

    monkeypatch.setattr("core.updater.download_update", fake_download_update)
    worker = svc.DownloadWorker("https://example.com/x.exe", tmp_path / "x.exe")
    got = []
    worker.progressed.connect(lambda done, total: got.append((done, total)))
    oks = []
    worker.finished_ok.connect(oks.append)
    worker.run()
    assert got == [(50, 100)]
    assert oks == [str(tmp_path / "x.exe")]


def test_check_async_spawns_and_starts_worker(qapp, monkeypatch):
    from gui import update_service as svc

    started = []

    class _Sig:
        def connect(self, fn):
            pass

    class FakeCheck:
        def __init__(self, current_version, parent=None):
            self.current_version = current_version
            self.finished_ok = _Sig()
            self.failed = _Sig()

        def isRunning(self):
            return False

        def start(self):
            started.append(self.current_version)

    monkeypatch.setattr(svc, "ReleaseCheckWorker", FakeCheck)
    service = svc.UpdateService("0.6.3")
    service.check_async()
    assert service._check is not None
    assert service._check.current_version == "0.6.3"
    assert started == ["0.6.3"]
