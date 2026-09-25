from __future__ import annotations

from pathlib import Path

from core.image_ops import ImageOpError
from core.tasks import Task, TaskKind
from gui import workers
from gui.workers import execute_task


def _src(tmp_path: Path, name: str = "a.mp4") -> Path:
    p = tmp_path / name
    p.write_bytes(b"x")
    return p


def test_video_convert_dispatch(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        workers.video_ops,
        "convert_video",
        lambda s, o, **kw: calls.append((s, o, kw)),
    )
    src = _src(tmp_path)
    out = tmp_path / "a.mkv"
    seen: list[int] = []
    task = Task(
        sources=[src],
        kind=TaskKind.VIDEO_CONVERT,
        params={"keep_audio": False},
        outputs=[out],
    )
    execute_task(task, progress_cb=seen.append)
    assert len(calls) == 1
    s, o, kw = calls[0]
    assert (s, o) == (src, out)
    assert kw["keep_audio"] is False
    assert kw["cancel_event"] is None
    assert seen == [100]


def test_video_to_gif_defaults_and_conversions(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        workers.video_ops,
        "video_to_gif",
        lambda s, o, **kw: calls.append((s, o, kw)),
    )
    src = _src(tmp_path)
    out = tmp_path / "a.gif"
    execute_task(Task(sources=[src], kind=TaskKind.VIDEO_TO_GIF, params={}, outputs=[out]))
    kw = calls[-1][2]
    assert kw["max_duration"] is None
    assert kw["fps"] == 15
    assert kw["width"] == 480

    execute_task(
        Task(
            sources=[src],
            kind=TaskKind.VIDEO_TO_GIF,
            params={"max_duration": 0, "fps": 12, "width": 320},
            outputs=[out],
        )
    )
    kw = calls[-1][2]
    assert kw["max_duration"] is None
    assert kw["fps"] == 12
    assert kw["width"] == 320
    assert kw["progress_cb"] is None


def test_video_to_gif_ticks_progress_per_source(tmp_path, monkeypatch):
    monkeypatch.setattr(workers.video_ops, "video_to_gif", lambda s, o, **kw: None)
    srcs = [_src(tmp_path, f"{i}.mp4") for i in range(2)]
    outs = [tmp_path / f"{i}.gif" for i in range(2)]
    seen: list[int] = []
    execute_task(
        Task(sources=srcs, kind=TaskKind.VIDEO_TO_GIF, params={}, outputs=outs),
        progress_cb=seen.append,
    )
    assert seen == [50, 100]


def test_video_extract_frames_rewrites_outputs(tmp_path, monkeypatch):
    produced = [tmp_path / "frames" / "f_0001.png"]
    monkeypatch.setattr(
        workers.video_ops,
        "extract_frames",
        lambda src, out_dir, **kw: produced,
    )
    src = _src(tmp_path)
    task = Task(
        sources=[src],
        kind=TaskKind.VIDEO_EXTRACT_FRAMES,
        params={"out_dir": str(tmp_path / "frames"), "at_seconds": [0.5, 2.0]},
        outputs=[],
    )
    seen: list[int] = []
    execute_task(task, progress_cb=seen.append)
    assert task.outputs == produced
    assert seen == [100]


def test_video_extract_frames_forwards_interval(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        workers.video_ops,
        "extract_frames",
        lambda src, out_dir, **kw: calls.append(kw) or [],
    )
    execute_task(
        Task(
            sources=[_src(tmp_path)],
            kind=TaskKind.VIDEO_EXTRACT_FRAMES,
            params={"out_dir": str(tmp_path), "every_seconds": 2.5, "ext": "jpg"},
        )
    )
    kw = calls[0]
    assert kw["every_seconds"] == 2.5
    assert kw["at_seconds"] is None
    assert kw["ext"] == "jpg"
    assert kw["clean_existing"] is True


def test_video_trim_casts_start_end_to_float(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        workers.video_ops, "trim_video", lambda s, o, a, b, **kw: calls.append((a, b))
    )
    execute_task(
        Task(
            sources=[_src(tmp_path)],
            kind=TaskKind.VIDEO_TRIM,
            params={"start": "1", "end": "2.5"},
            outputs=[tmp_path / "clip.mp4"],
        )
    )
    assert calls == [(1.0, 2.5)]


def test_gif_split_dispatch(tmp_path, monkeypatch):
    calls = []
    produced = [tmp_path / "out" / "frame_0001.png"]

    def fake_split(src, out_dir, **kw):
        calls.append((src, out_dir, kw))
        return produced

    monkeypatch.setattr(workers.gif_ops, "split_gif", fake_split)
    src = _src(tmp_path, "a.gif")
    task = Task(
        sources=[src],
        kind=TaskKind.GIF_SPLIT,
        params={"out_dir": str(tmp_path / "out"), "step": 2},
    )
    seen: list[int] = []
    execute_task(task, progress_cb=seen.append)
    assert task.outputs == produced
    s, out_dir, kw = calls[0]
    assert s == src
    assert out_dir == tmp_path / "out"
    assert kw["step"] == 2
    assert kw["clean_existing"] is True
    assert seen == [100]


def test_gif_merge_dispatch(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        workers.gif_ops,
        "merge_gif",
        lambda srcs, out, **kw: calls.append((list(srcs), out, kw)),
    )
    srcs = [_src(tmp_path, "a.png"), _src(tmp_path, "b.png")]
    out = tmp_path / "merged.gif"
    execute_task(
        Task(
            sources=srcs,
            kind=TaskKind.GIF_MERGE,
            params={"duration_ms": 50, "loop": 3, "reverse": 1},
            outputs=[out],
        )
    )
    got_srcs, got_out, kw = calls[0]
    assert got_srcs == srcs
    assert got_out == out
    assert kw["duration_ms"] == 50
    assert kw["loop"] == 3
    assert kw["reverse"] is True


def test_unpack_pkg_dispatch(tmp_path, monkeypatch):
    calls = []
    produced = [tmp_path / "out" / "file.wso"]

    def fake_extract(src, out_dir, **kw):
        calls.append((src, out_dir, kw))
        return produced

    monkeypatch.setattr(workers, "extract_pkg", fake_extract)
    src = _src(tmp_path, "a.pkg")
    task = Task(
        sources=[src],
        kind=TaskKind.UNPACK_PKG,
        params={"out_dir": str(tmp_path / "out")},
    )
    execute_task(task)
    assert task.outputs == produced
    assert calls[0][1] == tmp_path / "out"
    assert calls[0][2]["cancel_event"] is None


def test_unpack_tex_creates_dir_and_overwrites(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        workers,
        "extract_tex",
        lambda src, out_base, **kw: calls.append((src, out_base, kw)) or out_base,
    )
    src = _src(tmp_path, "a.tex")
    out_dir = tmp_path / "texout"
    task = Task(
        sources=[src],
        kind=TaskKind.UNPACK_TEX,
        params={"out_dir": str(out_dir)},
    )
    execute_task(task)
    assert out_dir.is_dir()
    _src_path, out_base, kw = calls[0]
    assert out_base == out_dir / "a"
    assert kw["overwrite"] is True
    assert task.outputs == [out_dir / "a"]


def test_unpack_mpkg_dispatch(tmp_path, monkeypatch):
    produced = [tmp_path / "out" / "x.mp4"]
    monkeypatch.setattr(workers, "extract_mpkg", lambda s, o, **kw: produced)
    task = Task(
        sources=[_src(tmp_path, "a.mpkg")],
        kind=TaskKind.UNPACK_MPKG,
        params={"out_dir": str(tmp_path / "out")},
    )
    execute_task(task)
    assert task.outputs == produced


def test_inpaint_image_dispatch(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        workers,
        "inpaint_image",
        lambda src, out, boxes: calls.append((src, out, boxes)) or out,
    )
    src = _src(tmp_path, "a.png")
    out = tmp_path / "clean.png"
    boxes = [(1, 1, 5, 5)]
    task = Task(
        sources=[src],
        kind=TaskKind.INPAINT_IMAGE,
        params={"out": str(out), "boxes": boxes},
    )
    execute_task(task)
    assert calls == [(src, out, boxes)]
    assert task.outputs == [out]


def test_remove_watermark_uses_provided_frame_size(tmp_path, monkeypatch):
    probe_calls = []
    monkeypatch.setattr(workers, "probe_video_size", lambda s: probe_calls.append(s))
    remove_calls = []

    def fake_remove(src, out, boxes, **kw):
        remove_calls.append(kw)
        return out

    monkeypatch.setattr(workers, "remove_video_watermark", fake_remove)
    src = _src(tmp_path, "a.mp4")
    out = tmp_path / "clean.mp4"
    task = Task(
        sources=[src],
        kind=TaskKind.REMOVE_VIDEO_WATERMARK,
        params={
            "out": str(out),
            "boxes": [(2, 2, 8, 8)],
            "frame_width": 1920,
            "frame_height": 1080,
        },
    )
    execute_task(task)
    assert probe_calls == []
    assert remove_calls[0]["frame_width"] == 1920
    assert remove_calls[0]["frame_height"] == 1080
    assert task.outputs == [out]


def test_remove_watermark_probes_size_when_missing(tmp_path, monkeypatch):
    probed = []
    monkeypatch.setattr(workers, "probe_video_size", lambda s: probed.append(s) or (640, 360))
    remove_calls = []

    def fake_remove(src, out, boxes, **kw):
        remove_calls.append(kw)
        return out

    monkeypatch.setattr(workers, "remove_video_watermark", fake_remove)
    task = Task(
        sources=[_src(tmp_path, "a.mp4")],
        kind=TaskKind.REMOVE_VIDEO_WATERMARK,
        params={"out": str(tmp_path / "clean.mp4"), "boxes": [(2, 2, 8, 8)]},
    )
    execute_task(task)
    assert len(probed) == 1
    assert remove_calls[0]["frame_width"] == 640
    assert remove_calls[0]["frame_height"] == 360


def test_image_edit_crop_dispatch(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        workers,
        "crop_image",
        lambda s, o, box: calls.append((s, o, box)) or o,
    )
    src = _src(tmp_path, "a.png")
    out = tmp_path / "crop.png"
    task = Task(
        sources=[src],
        kind=TaskKind.IMAGE_EDIT,
        params={"op": "crop", "box": (1, 2, 3, 4)},
        outputs=[out],
    )
    execute_task(task)
    assert calls == [(src, out, (1, 2, 3, 4))]
    assert task.outputs == [out]


def test_image_edit_watermark_ops_forward_kwargs(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        workers,
        "add_text_watermark",
        lambda s, o, **kw: calls.append(("text", kw)) or o,
    )
    monkeypatch.setattr(
        workers,
        "add_image_watermark",
        lambda s, o, **kw: calls.append(("image", kw)) or o,
    )
    src = _src(tmp_path, "a.png")
    execute_task(
        Task(
            sources=[src],
            kind=TaskKind.IMAGE_EDIT,
            params={"op": "text_watermark", "text": "水印", "pos": "br"},
            outputs=[tmp_path / "t.png"],
        )
    )
    execute_task(
        Task(
            sources=[src],
            kind=TaskKind.IMAGE_EDIT,
            params={"op": "image_watermark", "mark": "m.png", "pos": "tl"},
            outputs=[tmp_path / "m.png"],
        )
    )
    assert calls[0] == ("text", {"text": "水印", "pos": "br"})
    assert calls[1] == ("image", {"mark": "m.png", "pos": "tl"})


def test_image_edit_unknown_op_raises(tmp_path):
    task = Task(
        sources=[_src(tmp_path, "a.png")],
        kind=TaskKind.IMAGE_EDIT,
        params={"op": "rotate"},
        outputs=[tmp_path / "r.png"],
    )
    try:
        execute_task(task)
    except ImageOpError as exc:
        assert "未知编辑操作" in str(exc)
    else:
        raise AssertionError("expected ImageOpError for unknown op")


def test_unknown_task_kind_raises(tmp_path):
    task = Task(sources=[_src(tmp_path)], kind="bogus_kind")
    try:
        execute_task(task)
    except RuntimeError as exc:
        assert "未接入的任务类型" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for unknown kind")
