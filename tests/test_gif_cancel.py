import threading

from core.gif_ops import GifOpError, merge_gif, split_gif


def test_split_cancel_midway(gif_2f, tmp_path):
    ev = threading.Event()
    ev.set()
    try:
        split_gif(gif_2f, tmp_path / "c", cancel_event=ev)
        raise AssertionError("should raise")
    except GifOpError as e:
        assert "取消" in str(e)


def test_merge_cancel_immediate(gif_2f, tmp_path):
    frames = split_gif(gif_2f, tmp_path / "f")
    ev = threading.Event()
    ev.set()
    try:
        merge_gif(frames, tmp_path / "m.gif", cancel_event=ev)
        raise AssertionError("should raise")
    except GifOpError as e:
        assert "取消" in str(e)
