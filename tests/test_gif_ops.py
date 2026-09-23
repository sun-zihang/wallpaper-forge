from PIL import Image

from core.gif_ops import merge_gif, split_gif


def test_split_two_frames(gif_2f, tmp_path):
    frames = split_gif(gif_2f, tmp_path / "f")
    assert len(frames) == 2
    assert frames[0].name == "frame_0001.png"


def test_split_step(gif_2f, tmp_path):
    assert len(split_gif(gif_2f, tmp_path / "f", step=2)) == 1


def test_merge_roundtrip(gif_2f, tmp_path):
    frames = split_gif(gif_2f, tmp_path / "f")
    out = merge_gif(frames, tmp_path / "m.gif", duration_ms=50)
    im = Image.open(out)
    n = 0
    try:
        while True:
            im.seek(n)
            n += 1
    except EOFError:
        pass
    assert n == 2


def test_merge_reverse(gif_2f, tmp_path):
    frames = split_gif(gif_2f, tmp_path / "f")
    out = merge_gif(frames, tmp_path / "r.gif", reverse=True)
    assert out.exists()
