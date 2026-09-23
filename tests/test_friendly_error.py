from gui.workers import friendly_error
from core.video_ops import VideoOpError


def test_friendly_error_appends_stderr_tail():
    e = VideoOpError("FFmpeg 编码失败", "x264 [error]: something bad\nFinal line reason")
    msg = friendly_error(e)
    assert "Final line reason" in msg
    assert "视频处理失败" in msg


def test_friendly_error_cancelled_omits_tail():
    e = VideoOpError("已取消", "noise line")
    msg = friendly_error(e)
    assert "noise line" not in msg


def test_friendly_error_unknown():
    assert "未知错误" in friendly_error(RuntimeError("boom"))
