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


def test_friendly_error_maps_remaining_labels():
    from core.gif_ops import GifOpError
    from core.rewatermark import RewatermarkError
    from core.video_ops import VideoOpError
    from core.we_mpkg import WeMpkgError
    from core.we_tex import WeTexError

    assert "视频处理失败" in friendly_error(VideoOpError("编码炸了"))
    assert "GIF 处理失败" in friendly_error(GifOpError("帧损坏"))
    assert "MPKG 解包失败" in friendly_error(WeMpkgError("坏包"))
    assert "TEX 解析失败" in friendly_error(WeTexError("坏纹理"))
    assert "去水印失败" in friendly_error(RewatermarkError("蒙版无效"))


def test_friendly_error_empty_detail_falls_back_to_label():
    from core.we_tex import WeTexError

    assert friendly_error(WeTexError("")) == "TEX 解析失败"


def test_friendly_error_prefers_specific_label_over_oserror():
    msg = friendly_error(PermissionError("locked"))
    assert "没有文件访问权限" in msg
    assert "磁盘或文件系统错误" not in msg
    msg = friendly_error(FileNotFoundError("gone"))
    assert "文件不存在" in msg
    assert "磁盘或文件系统错误" not in msg
