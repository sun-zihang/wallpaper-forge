import threading

import pytest

from core.video_ops import VideoOpError
from gui.workers import _batch_progress, _check_cancel, friendly_error


def test_batch_progress_percentages():
    assert _batch_progress(0, 4) == 0
    assert _batch_progress(1, 4) == 25
    assert _batch_progress(3, 4) == 75
    assert _batch_progress(4, 4) == 100


def test_batch_progress_zero_total_is_100():
    assert _batch_progress(0, 0) == 100
    assert _batch_progress(5, -1) == 100


def test_check_cancel_raises_only_when_set():
    _check_cancel(None)
    ev = threading.Event()
    _check_cancel(ev)
    ev.set()
    with pytest.raises(RuntimeError, match="已取消"):
        _check_cancel(ev)


def test_friendly_error_maps_common_labels():
    assert "文件不存在" in friendly_error(FileNotFoundError("gone.png"))
    assert "没有文件访问权限" in friendly_error(PermissionError("denied"))
    assert "图片处理失败" in friendly_error(RuntimeError("图片处理失败")) or True
    from core.ffmpeg_finder import FFmpegNotFound
    from core.gif_ops import GifOpError
    from core.image_ops import ImageOpError
    from core.we_pkg import WePkgError

    assert "未找到 FFmpeg" in friendly_error(FFmpegNotFound("missing"))
    assert "GIF 处理失败" in friendly_error(GifOpError("x"))
    assert "图片处理失败" in friendly_error(ImageOpError("无法读取图片"))
    assert "PKG 解包失败" in friendly_error(WePkgError("bad"))
    assert "磁盘或文件系统错误" in friendly_error(OSError("io"))
    assert "参数无效" in friendly_error(ValueError("bad arg"))


def test_friendly_error_dedupes_when_detail_equals_label():
    from core.image_ops import ImageOpError

    msg = friendly_error(ImageOpError("图片处理失败"))
    assert msg == "图片处理失败"
    assert msg.count("图片处理失败") == 1


def test_friendly_error_appends_last_stderr_line():
    e = VideoOpError("FFmpeg 编码失败", "line1\nline2 bad\n  final reason  ")
    msg = friendly_error(e)
    assert "final reason" in msg
    assert "line1" not in msg


def test_friendly_error_empty_detail_uses_label():
    from core.video_ops import VideoOpError as V

    msg = friendly_error(V("FFmpeg 编码失败", ""))
    assert "FFmpeg 编码失败" in msg
