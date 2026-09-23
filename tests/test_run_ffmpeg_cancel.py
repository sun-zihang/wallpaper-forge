import threading

import pytest

from core.ffmpeg_finder import FFmpegNotFound, find_ffmpeg
from core.video_ops import VideoOpError, probe_video_duration, run_ffmpeg


@pytest.fixture
def tiny_mp4(tmp_path):
    p = tmp_path / "tiny.mp4"
    try:
        ff = find_ffmpeg()
    except FFmpegNotFound:
        pytest.skip("ffmpeg not available")
    import subprocess

    r = subprocess.run(
        [
            str(ff),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=64x48:rate=10:duration=1",
            "-pix_fmt",
            "yuv420p",
            str(p),
        ],
        capture_output=True,
    )
    if r.returncode != 0 or not p.exists():
        pytest.skip("ffmpeg cannot encode test clip")
    return p


def test_probe_duration_positive(tiny_mp4):
    d = probe_video_duration(tiny_mp4)
    assert d is not None and d > 0


def test_cancel_kills_and_cleans_partial(tiny_mp4, tmp_path):
    out = tmp_path / "partial.mp4"
    ev = threading.Event()
    ev.set()  # cancel immediately
    with pytest.raises(VideoOpError) as ei:
        run_ffmpeg(
            ["-i", str(tiny_mp4), "-c:v", "libx264", str(out)],
            cancel_event=ev,
            cleanup=out,
        )
    assert "取消" in str(ei.value)
    assert not out.exists()
