"""run_ffmpeg internals with a fake Popen (no real ffmpeg process)."""

from __future__ import annotations

import io
import subprocess
import threading
from pathlib import Path

import pytest

from core.video_ops import VideoOpError, _cleanup_partial, run_ffmpeg


class FakeProc:
    def __init__(
        self,
        stdout_lines=(),
        stderr_text="",
        returncode=0,
        on_wait=None,
        wait_timeouts=0,
    ):
        self.stdout = iter(stdout_lines) if stdout_lines is not None else None
        self.stderr = io.StringIO(stderr_text)
        self.returncode = returncode
        self._on_wait = on_wait
        self._timeouts = wait_timeouts
        self.killed = False

    def wait(self, timeout=None):
        if self._on_wait is not None:
            cb, self._on_wait = self._on_wait, None
            cb()
        if self._timeouts > 0:
            self._timeouts -= 1
            raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=timeout or 0)
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9

    def poll(self):
        return self.returncode


def _patch(monkeypatch, proc, cmds=None):
    if cmds is None:
        cmds = []

    def fake_popen(cmd, **kw):
        cmds.append((cmd, kw))
        return proc

    monkeypatch.setattr("core.video_ops.subprocess.Popen", fake_popen)
    monkeypatch.setattr("core.video_ops.find_ffmpeg", lambda: Path("ffmpeg"))
    return cmds


def test_progress_mode_parses_out_time_and_completes(monkeypatch, tmp_path):
    lines = [
        "out_time_us=5000000\n",
        "out_time_us=5000000\n",
        "out_time_us=9000000\n",
        "out_time_us=not-a-number\n",
        "progress=end\n",
    ]
    proc = FakeProc(stdout_lines=lines, returncode=0)
    cmds = _patch(monkeypatch, proc)
    cleanup = tmp_path / "o.mp4"
    cleanup.write_bytes(b"x")
    pcts: list[int] = []
    run_ffmpeg(
        ["-i", "a.mp4", "o.mp4"],
        progress_cb=pcts.append,
        duration=10.0,
        cleanup=cleanup,
    )
    cmd, kw = cmds[0]
    assert "-progress" in cmd and "pipe:1" in cmd and "-nostats" in cmd
    assert kw["stdout"] is subprocess.PIPE
    assert pcts == [50, 90, 100, 100]  # dup + bad value skipped; final 100 twice
    assert cleanup.exists()  # success never deletes cleanup target


def test_progress_mode_cancel_kills_and_cleans(monkeypatch, tmp_path):
    ev = threading.Event()
    ev.set()
    proc = FakeProc(stdout_lines=["out_time_us=1000000\n"], returncode=0)
    _patch(monkeypatch, proc)
    cleanup = tmp_path / "o.mp4"
    cleanup.write_bytes(b"x")
    with pytest.raises(VideoOpError, match="已取消"):
        run_ffmpeg(
            ["-i", "a.mp4", "o.mp4"],
            cancel_event=ev,
            progress_cb=lambda _p: None,
            duration=10.0,
            cleanup=cleanup,
        )
    assert proc.killed
    assert not cleanup.exists()


def test_progress_mode_wait_timeout_kills_then_waits(monkeypatch, tmp_path):
    proc = FakeProc(
        stdout_lines=["progress=end\n"],
        returncode=0,
        wait_timeouts=1,
    )
    _patch(monkeypatch, proc)
    cleanup = tmp_path / "o.mp4"
    cleanup.write_bytes(b"x")
    # kill() marks the fake as failed; run_ffmpeg must reap it and surface the error
    with pytest.raises(VideoOpError, match="FFmpeg 编码失败"):
        run_ffmpeg(
            ["-i", "a.mp4", "o.mp4"],
            progress_cb=lambda _p: None,
            duration=10.0,
            cleanup=cleanup,
        )
    assert proc.killed
    assert not cleanup.exists()


def test_failure_raises_with_stderr_tail(monkeypatch, tmp_path):
    stderr_text = "\n".join(f"err{i}" for i in range(12)) + "\n"
    proc = FakeProc(
        stdout_lines=["progress=end\n"],
        stderr_text=stderr_text,
        returncode=1,
    )
    _patch(monkeypatch, proc)
    cleanup = tmp_path / "o.mp4"
    cleanup.write_bytes(b"x")
    with pytest.raises(VideoOpError) as ei:
        run_ffmpeg(
            ["-i", "a.mp4", "o.mp4"],
            progress_cb=lambda _p: None,
            duration=10.0,
            cleanup=cleanup,
        )
    assert "FFmpeg 编码失败" in str(ei.value)
    assert "err11" in ei.value.stderr_tail
    assert "err0" not in ei.value.stderr_tail  # tail keeps last 8 lines
    assert not cleanup.exists()


def test_failure_after_cancel_reports_cancelled(monkeypatch, tmp_path):
    ev = threading.Event()
    proc = FakeProc(
        stdout_lines=["progress=end\n"],
        returncode=1,
        on_wait=lambda: ev.set(),
    )
    _patch(monkeypatch, proc)
    with pytest.raises(VideoOpError, match="已取消"):
        run_ffmpeg(
            ["-i", "a.mp4", "o.mp4"],
            cancel_event=ev,
            progress_cb=lambda _p: None,
            duration=10.0,
            cleanup=tmp_path / "o.mp4",
        )


def test_no_progress_mode_success_keeps_quiet(monkeypatch, tmp_path):
    proc = FakeProc(stdout_lines=None, stderr_text="done\n", returncode=0)
    cmds = _patch(monkeypatch, proc)
    run_ffmpeg(["-i", "a.mp4", "o.mp4"], progress_cb=None, duration=None)
    cmd, _kw = cmds[0]
    assert "-progress" not in cmd


def test_no_progress_mode_cancel_pre_set(monkeypatch, tmp_path):
    ev = threading.Event()
    ev.set()
    proc = FakeProc(stdout_lines=None, returncode=0)
    _patch(monkeypatch, proc)
    cleanup = tmp_path / "o.mp4"
    cleanup.write_bytes(b"x")
    with pytest.raises(VideoOpError, match="已取消"):
        run_ffmpeg(
            ["-i", "a.mp4", "o.mp4"],
            cancel_event=ev,
            progress_cb=None,
            duration=None,
            cleanup=cleanup,
        )
    assert proc.killed
    assert not cleanup.exists()


def test_progress_cb_exception_kills_live_process(monkeypatch, tmp_path):
    proc = FakeProc(stdout_lines=["out_time_us=1000000\n"], returncode=None)
    _patch(monkeypatch, proc)

    def boom(_pct):
        raise RuntimeError("callback exploded")

    with pytest.raises(RuntimeError, match="callback exploded"):
        run_ffmpeg(
            ["-i", "a.mp4", "o.mp4"],
            progress_cb=boom,
            duration=10.0,
            cleanup=tmp_path / "o.mp4",
        )
    assert proc.killed  # finally block must terminate the still-running proc


def test_popen_oserror_wrapped(monkeypatch):
    def boom(cmd, **kw):
        raise FileNotFoundError("no ffmpeg binary")

    monkeypatch.setattr("core.video_ops.subprocess.Popen", boom)
    monkeypatch.setattr("core.video_ops.find_ffmpeg", lambda: Path("ffmpeg"))
    with pytest.raises(VideoOpError, match="无法启动 ffmpeg"):
        run_ffmpeg(["-i", "a.mp4", "o.mp4"])


def test_cleanup_partial_unlink_oserror_swallowed(tmp_path, monkeypatch):
    p = tmp_path / "locked.part"
    p.write_bytes(b"x")

    def locked(*_a, **_k):
        raise OSError("file locked")

    monkeypatch.setattr(Path, "unlink", locked)
    _cleanup_partial(p)  # must not raise
    assert p.exists()
