from PIL import Image

from core.gif_ops import merge_gif, split_gif
from core.safeio import part_path


def test_split_two_frames(gif_2f, tmp_path):
    frames = split_gif(gif_2f, tmp_path / "f")
    assert len(frames) == 2
    assert frames[0].name == "frame_0001.png"


def test_split_step(gif_2f, tmp_path):
    assert len(split_gif(gif_2f, tmp_path / "f", step=2)) == 1


def test_split_clean_existing_removes_stale_frames(gif_2f, tmp_path):
    out = tmp_path / "f"
    out.mkdir()
    (out / "frame_0009.png").write_bytes(b"stale")
    (out / "keepme.txt").write_bytes(b"keep")
    frames = split_gif(gif_2f, out, clean_existing=True)
    assert len(frames) == 2
    assert not (out / "frame_0009.png").exists()
    assert (out / "keepme.txt").exists()


def test_split_without_clean_keeps_stale_frames(gif_2f, tmp_path):
    out = tmp_path / "f"
    out.mkdir()
    (out / "frame_0009.png").write_bytes(b"stale")
    split_gif(gif_2f, out)
    assert (out / "frame_0009.png").exists()


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


def test_merge_inplace_same_path(gif_2f, tmp_path):
    # 把源 GIF 也作为合并输入且输出路径相同（unified 指向源目录的场景）
    out_path = gif_2f  # a.gif
    frames = split_gif(gif_2f, tmp_path / "f")
    # 用 frames[0] 之外再塞一个同名目标：直接 merge 到 gif_2f
    out = merge_gif(frames + [gif_2f], out_path, duration_ms=50)
    assert out == gif_2f
    assert out.exists()
    assert not part_path(gif_2f).exists()
