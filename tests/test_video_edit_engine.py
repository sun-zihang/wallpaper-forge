import pytest

from gui.video_edit.engine import (
    AdjustParamsCommand,
    EditEngine,
    MoveClipCommand,
    RemoveClipCommand,
    SplitClipCommand,
    TrimClipCommand,
)
from gui.video_edit.model import Clip, TimelineModel, Track


def make_timeline():
    tl = TimelineModel(id="tl1", name="测试")
    t1 = Track(id="t1", type="video", name="视频轨 1")
    t1.add_clip(Clip(id="c1", source_file="a.mp4", timeline_in=0, source_in=0, source_out=10))
    t1.add_clip(Clip(id="c2", source_file="b.mp4", timeline_in=10, source_in=0, source_out=8))
    t2 = Track(id="t2", type="video", name="视频轨 2")
    t2.add_clip(Clip(id="c3", source_file="c.mp4", timeline_in=0, source_in=2, source_out=6))
    tl.add_track(t1)
    tl.add_track(t2)
    return tl


def get_track(tl, track_id):
    return next(t for t in tl.tracks if t.id == track_id)


def test_split_clip():
    tl = make_timeline()
    engine = EditEngine(tl)
    cmd = SplitClipCommand("c1", 4)
    engine.execute(cmd)
    t1 = tl.get_clip_track("c1")
    assert len(t1.clips) == 3
    c1 = tl.find_clip("c1")
    assert c1.source_in == 0
    assert c1.source_out == 4
    assert c1.duration == 4
    c2 = tl.find_clip(cmd.new_clip_id)
    assert c2.source_in == 4
    assert c2.source_out == 10
    assert c2.duration == 6
    assert c2.timeline_in == 4
    assert tl.duration == 18


def test_undo_redo_split():
    tl = make_timeline()
    engine = EditEngine(tl)
    engine.execute(SplitClipCommand("c1", 4))
    assert engine.undo() is True
    t1 = tl.get_clip_track("c1")
    assert len(t1.clips) == 2
    c1 = tl.find_clip("c1")
    assert (c1.source_in, c1.source_out) == (0, 10)
    assert engine.redo() is True
    assert len(tl.get_clip_track("c1").clips) == 3


def test_remove_clip_undo_restores_index():
    tl = make_timeline()
    engine = EditEngine(tl)
    engine.execute(RemoveClipCommand("c1"))
    assert tl.find_clip("c1") is None
    assert [c.id for c in get_track(tl, "t1").clips] == ["c2"]
    engine.undo()
    t1 = get_track(tl, "t1")
    assert [c.id for c in t1.clips] == ["c1", "c2"]
    assert t1.clips[0].source_file == "a.mp4"


def test_remove_missing_clip_is_noop():
    tl = make_timeline()
    engine = EditEngine(tl)
    engine.execute(RemoveClipCommand("nope"))
    assert engine.undo() is True
    assert tl.find_clip("c1") is not None
    assert tl.duration == 18


def test_move_clip_undo_redo():
    tl = make_timeline()
    engine = EditEngine(tl)
    engine.execute(MoveClipCommand("c1", "t2", 5))
    c1 = tl.find_clip("c1")
    assert tl.get_clip_track("c1").id == "t2"
    assert c1.timeline_in == 5
    assert [c.id for c in get_track(tl, "t1").clips] == ["c2"]
    engine.undo()
    assert tl.get_clip_track("c1").id == "t1"
    assert c1.timeline_in == 0
    assert [c.id for c in get_track(tl, "t1").clips] == ["c1", "c2"]
    engine.redo()
    assert tl.get_clip_track("c1").id == "t2"
    assert c1.timeline_in == 5


def test_adjust_params_undo_restores():
    tl = make_timeline()
    engine = EditEngine(tl)
    cmd = AdjustParamsCommand("c1", {"filters": {"brightness": 0.5}, "speed": 2.0})
    engine.execute(cmd)
    c1 = tl.find_clip("c1")
    assert c1.params["filters"]["brightness"] == 0.5
    assert c1.speed == 2.0
    engine.undo()
    assert c1.params["filters"]["brightness"] == 0
    assert c1.speed == 1.0
    engine.redo()
    assert c1.params["filters"]["brightness"] == 0.5
    assert c1.speed == 2.0


def test_adjust_params_overlay():
    tl = make_timeline()
    engine = EditEngine(tl)
    overlay = {
        "type": "text",
        "text": "你好",
        "position": {"x": 50, "y": 50},
        "fontSize": 24,
        "fontColor": "#ffffff",
        "opacity": 0.8,
    }
    engine.execute(AdjustParamsCommand("c1", {"overlay": overlay}))
    assert tl.find_clip("c1").params["overlay"]["text"] == "你好"
    engine.undo()
    assert tl.find_clip("c1").params["overlay"] is None


def test_trim_clip_undo():
    tl = make_timeline()
    engine = EditEngine(tl)
    engine.execute(TrimClipCommand("c1", 2, 8))
    c1 = tl.find_clip("c1")
    assert (c1.source_in, c1.source_out) == (2, 8)
    assert c1.duration == 6
    engine.undo()
    assert (c1.source_in, c1.source_out) == (0, 10)
    engine.redo()
    assert (c1.source_in, c1.source_out) == (2, 8)


def test_undo_redo_empty_stacks():
    engine = EditEngine(make_timeline())
    assert engine.undo() is False
    assert engine.redo() is False


def test_execute_clears_redo_stack():
    tl = make_timeline()
    engine = EditEngine(tl)
    engine.execute(SplitClipCommand("c1", 4))
    engine.undo()
    assert engine.redo() is True
    engine.undo()
    engine.execute(RemoveClipCommand("c2"))
    assert engine.redo_stack == []


def test_undo_stack_capped_at_50():
    tl = make_timeline()
    engine = EditEngine(tl)
    for i in range(55):
        engine.execute(AdjustParamsCommand("c1", {"filters": {"brightness": i / 100}}))
    assert len(engine.undo_stack) == 50
    assert tl.find_clip("c1").params["filters"]["brightness"] == pytest.approx(0.54)
    undos = 0
    while engine.undo():
        undos += 1
    assert undos == 50
    assert tl.find_clip("c1").params["filters"]["brightness"] == pytest.approx(0.04)
