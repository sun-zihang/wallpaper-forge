from gui.video_edit.model import Clip, TimelineModel, Track, create_default_params


def make_clip(**overrides):
    defaults = dict(
        id="c1",
        source_file="test.mp4",
        timeline_in=0,
        source_in=0,
        source_out=5,
        speed=1.0,
        params=create_default_params(),
    )
    defaults.update(overrides)
    return Clip(**defaults)


def test_clip_duration():
    clip = make_clip(source_in=0, source_out=10, speed=2.0)
    assert clip.duration == 5.0


def test_clip_split_at():
    clip = make_clip(source_in=0, source_out=10, speed=1.0)
    c1, c2 = clip.split_at(4)
    assert c1.source_out == 4
    assert c2.source_in == 4
    assert c1.duration + c2.duration == clip.duration


def test_track_add_remove_clip():
    track = Track(id="t1", type="video", name="视频轨")
    clip = make_clip()
    track.add_clip(clip)
    assert len(track.clips) == 1
    track.remove_clip("c1")
    assert len(track.clips) == 0


def test_timeline_duration():
    tl = TimelineModel(id="tl1", name="测试")
    track = Track(id="t1", type="video", name="视频轨")
    track.add_clip(make_clip(timeline_in=0, source_out=5))
    track.add_clip(make_clip(id="c2", timeline_in=5, source_in=0, source_out=8))
    tl.add_track(track)
    assert tl.duration == 13


def test_timeline_find_clip():
    tl = TimelineModel(id="tl1")
    t1 = Track(id="t1", type="video")
    t2 = Track(id="t2", type="audio")
    t1.add_clip(make_clip(id="c1"))
    t2.add_clip(make_clip(id="c2"))
    tl.add_track(t1)
    tl.add_track(t2)
    assert tl.find_clip("c2").id == "c2"
    assert tl.get_clip_track("c2").id == "t2"


def test_serialization():
    tl = TimelineModel(id="tl1", name="测试")
    track = Track(id="t1", type="video", name="视频轨")
    track.add_clip(make_clip(id="c1", timeline_in=2, source_in=1, source_out=6, speed=1.5))
    tl.add_track(track)
    data = tl.to_dict()
    tl2 = TimelineModel.from_dict(data)
    assert tl2.duration == tl.duration
    assert tl2.find_clip("c1").source_in == 1
    assert tl2.find_clip("c1").speed == 1.5


def test_create_default_params():
    p = create_default_params()
    assert p["transform"]["rotation"] == 0
    assert p["transform"]["flip_h"] is False
    assert p["transform"]["scale"] == 1.0
    assert p["transform"]["crop"] is None
    assert p["audio"]["volume"] == 1.0
    assert p["audio"]["fade_in"] == 0
    assert p["audio"]["fade_out"] == 0
    assert p["overlay"] is None
    assert p["filters"]["brightness"] == 0
    assert p["filters"]["contrast"] == 0
    assert p["filters"]["grayscale"] is False
