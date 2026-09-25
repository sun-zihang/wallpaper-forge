import subprocess
from pathlib import Path

import pytest

from core.ffmpeg_finder import FFmpegNotFound, find_ffmpeg
from core.safeio import part_path
from core.video_ops import (
    VideoOpError,
    convert_video,
    extract_frames,
    trim_video,
    video_to_gif,
)


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
    out = video_to_gif(tiny_mp4, tmp_path / "o.gif", fps=5, width=32, max_duration=1)
    assert out.exists()


def test_extract_frames(tiny_mp4, tmp_path):
    outs = extract_frames(tiny_mp4, tmp_path / "fr", every_seconds=0.5)
    assert len(outs) >= 1 and outs[0].suffix == ".png"


def test_extract_frames_clean_existing_removes_stale(tiny_mp4, tmp_path):
    out = tmp_path / "fr"
    out.mkdir()
    (out / "frame_0009.png").write_bytes(b"stale")
    (out / "at_0.5s_01.png").write_bytes(b"stale")
    (out / "keepme.png").write_bytes(b"keep")
    outs = extract_frames(tiny_mp4, out, every_seconds=0.5, clean_existing=True)
    assert outs
    assert not (out / "frame_0009.png").exists()
    assert not (out / "at_0.5s_01.png").exists()
    assert (out / "keepme.png").exists()


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


def test_inplace_rejects_empty_ffmpeg_output(tmp_path, monkeypatch):
    # ffmpeg "成功" 但只写出 0 字节 .part：不得 replace 覆盖源文件
    src = tmp_path / "clip.mp4"
    payload = b"\x00" * 32
    src.write_bytes(payload)

    def fake_run_ffmpeg(args, **kwargs):
        Path(args[-1]).write_bytes(b"")

    monkeypatch.setattr("core.video_ops.run_ffmpeg", fake_run_ffmpeg)
    monkeypatch.setattr("core.video_ops.probe_video_duration", lambda p: None)

    with pytest.raises(VideoOpError, match="输出为空"):
        convert_video(src, src, keep_audio=False)
    assert src.read_bytes() == payload
    assert not part_path(src).exists()

    with pytest.raises(VideoOpError, match="输出为空"):
        trim_video(src, src, 0, 0.4)
    assert src.read_bytes() == payload
    assert not part_path(src).exists()


def test_convert_rejects_unsupported_ext(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    with pytest.raises(VideoOpError, match="不支持的输出格式"):
        convert_video(src, tmp_path / "o.avi")


def test_convert_missing_source_raises(tmp_path):
    with pytest.raises(VideoOpError, match="输入文件不存在"):
        convert_video(tmp_path / "nope.mp4", tmp_path / "o.mp4")


def test_video_to_gif_rejects_bad_fps_and_width(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    with pytest.raises(VideoOpError, match="GIF 帧率"):
        video_to_gif(src, tmp_path / "o.gif", fps=0)
    with pytest.raises(VideoOpError, match="GIF 帧率"):
        video_to_gif(src, tmp_path / "o.gif", fps=51)
    with pytest.raises(VideoOpError, match="GIF 宽度"):
        video_to_gif(src, tmp_path / "o.gif", width=15)


def test_extract_frames_rejects_bad_ext_interval_and_negative_time(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    with pytest.raises(VideoOpError, match="不支持的截帧格式"):
        extract_frames(src, tmp_path / "fr", ext="bmp")
    with pytest.raises(VideoOpError, match="请指定截帧间隔"):
        extract_frames(src, tmp_path / "fr")
    with pytest.raises(VideoOpError, match="截帧时间不能为负"):
        extract_frames(src, tmp_path / "fr", at_seconds=[-0.1])


def test_trim_rejects_invalid_range(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    with pytest.raises(VideoOpError, match="片段范围无效"):
        trim_video(src, tmp_path / "o.mp4", 1.0, 0.5)
    with pytest.raises(VideoOpError, match="片段范围无效"):
        trim_video(src, tmp_path / "o.mp4", -1, 0.5)


def test_probe_duration_returns_none_without_ffmpeg(monkeypatch):
    from core.video_ops import probe_video_duration

    def _raise():
        from core.ffmpeg_finder import FFmpegNotFound

        raise FFmpegNotFound("missing")

    monkeypatch.setattr("core.video_ops.find_ffmpeg", _raise)
    assert probe_video_duration(Path("any.mp4")) is None


def test_cleanup_partial_silent(tmp_path):
    from core.video_ops import _cleanup_partial

    _cleanup_partial(None)
    _cleanup_partial(tmp_path / "missing.part")
    p = tmp_path / "x.part"
    p.write_bytes(b"x")
    _cleanup_partial(p)
    assert not p.exists()
