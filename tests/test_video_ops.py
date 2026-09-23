import subprocess

import pytest

from core.ffmpeg_finder import FFmpegNotFound, find_ffmpeg
from core.safeio import part_path
from core.video_ops import convert_video, extract_frames, trim_video, video_to_gif


@pytest.fixture
def tiny_mp4(tmp_path):
    p = tmp_path / "tiny.mp4"
    try:
        ff = find_ffmpeg()
    except FFmpegNotFound:
        pytest.skip("ffmpeg not available")
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


def test_convert_to_webm(tiny_mp4, tmp_path):
    out = convert_video(tiny_mp4, tmp_path / "o.webm", keep_audio=False)
    assert out.exists() and out.stat().st_size > 0


def test_video_to_gif(tiny_mp4, tmp_path):
    out = video_to_gif(
        tiny_mp4, tmp_path / "o.gif", fps=5, width=32, max_duration=1
    )
    assert out.exists()


def test_extract_frames(tiny_mp4, tmp_path):
    outs = extract_frames(tiny_mp4, tmp_path / "fr", every_seconds=0.5)
    assert len(outs) >= 1 and outs[0].suffix == ".png"


def test_trim(tiny_mp4, tmp_path):
    out = trim_video(tiny_mp4, tmp_path / "t.mp4", 0, 0.4)
    assert out.exists()


def test_convert_inplace_uses_part(tiny_mp4, tmp_path):
    import shutil

    src = tmp_path / "clip.mp4"
    shutil.copy(tiny_mp4, src)
    before = src.stat().st_size
    out = convert_video(src, src, keep_audio=False)
    assert out == src
    assert src.stat().st_size > 0
    assert not part_path(src).exists()
    assert before > 0


def test_trim_inplace_uses_part(tiny_mp4, tmp_path):
    import shutil

    src = tmp_path / "clip.mp4"
    shutil.copy(tiny_mp4, src)
    out = trim_video(src, src, 0, 0.4)
    assert out == src
    assert not part_path(src).exists()
