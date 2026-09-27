import threading
from unittest import mock

import pytest

from core.video_ops import VideoOpError
from gui.video_edit.exporter import NativeExporter
from gui.video_edit.model import Clip, TimelineModel, Track


def make_timeline(muted_track=False, non_video=False):
    tl = TimelineModel(id="tl1", name="测试")
    t1 = Track(id="t1", type="video", name="视频轨")
    t1.add_clip(Clip(id="c1", source_file="a.mp4", timeline_in=0, source_in=0, source_out=5))
    tl.add_track(t1)
    if muted_track:
        tm = Track(id="tm", type="video", name="静音轨", muted=True)
        tm.add_clip(Clip(id="cm", source_file="m.mp4", timeline_in=0, source_in=0, source_out=5))
        tl.add_track(tm)
    if non_video:
        ta = Track(id="ta", type="audio", name="音频轨")
        ta.add_clip(Clip(id="ca", source_file="s.mp3", timeline_in=0, source_in=0, source_out=5))
        tl.add_track(ta)
    return tl


def make_fake_ffmpeg(recorded):
    def fake_run_ffmpeg(args, **kwargs):
        recorded["calls"].append(list(args))
        if "-f" in args and args[args.index("-f") + 1] == "concat":
            with open(args[args.index("-i") + 1], encoding="utf-8") as f:
                recorded["concat"] = f.read()
        with open(args[-1], "wb") as f:
            f.write(b"fake-video-bytes")

    return fake_run_ffmpeg


def test_export_single_clip_no_processing():
    tl = make_timeline()
    recorded = {"calls": [], "concat": None}
    exporter = NativeExporter()
    with mock.patch("gui.video_edit.exporter.run_ffmpeg", side_effect=make_fake_ffmpeg(recorded)):
        data = exporter.export(tl, {"format": "mp4"})
    assert data == b"fake-video-bytes"
    assert len(recorded["calls"]) == 1
    args = recorded["calls"][0]
    assert args[:4] == ["-i", "a.mp4", "-c", "copy"]
    assert recorded["concat"] is None


def test_export_progress():
    tl = make_timeline()
    progress = []
    exporter = NativeExporter()
    with mock.patch(
        "gui.video_edit.exporter.run_ffmpeg",
        side_effect=make_fake_ffmpeg({"calls": [], "concat": None}),
    ):
        exporter.export(tl, {"format": "mp4"}, on_progress=lambda p, m: progress.append((p, m)))
    assert progress[0] == (0, "预处理片段 1/1")
    assert progress[1] == (50, "合成最终视频…")
    assert progress[-1] == (100, "导出完成")


def test_export_cancel_raises():
    tl = make_timeline()
    cancel = threading.Event()
    cancel.set()
    exporter = NativeExporter()
    with (
        mock.patch("gui.video_edit.exporter.run_ffmpeg"),
        pytest.raises(VideoOpError, match="已取消"),
    ):
        exporter.export(tl, {"format": "mp4"}, cancel_event=cancel)


def test_muted_and_audio_tracks_skipped():
    tl = make_timeline(muted_track=True, non_video=True)
    recorded = {"calls": [], "concat": None}
    exporter = NativeExporter()
    with mock.patch("gui.video_edit.exporter.run_ffmpeg", side_effect=make_fake_ffmpeg(recorded)):
        exporter.export(tl, {"format": "mp4"})
    args = recorded["calls"][0]
    assert args[1] == "a.mp4"
    assert "m.mp4" not in args
    assert "s.mp3" not in args


def test_process_clip_args_and_settings():
    tl = make_timeline()
    clip = tl.find_clip("c1")
    clip.params["audio"]["volume"] = 0.5
    clip.params["filters"]["brightness"] = 0.2
    recorded = {"calls": [], "concat": None}
    exporter = NativeExporter()
    settings = {
        "format": "mp4",
        "video_codec": "libx265",
        "preset": "fast",
        "crf": 20,
        "audio_codec": "libopus",
    }
    with mock.patch("gui.video_edit.exporter.run_ffmpeg", side_effect=make_fake_ffmpeg(recorded)):
        exporter.export(tl, settings)
    process_args = recorded["calls"][0]
    assert process_args[:7] == ["-i", "a.mp4", "-ss", "0", "-t", "5", "-vf"]
    assert "brightness=0.2" in process_args[7]
    assert process_args[process_args.index("-af") + 1] == "volume=0.5"
    assert process_args[process_args.index("-c:v") + 1] == "libx265"
    assert process_args[process_args.index("-preset") + 1] == "fast"
    assert process_args[process_args.index("-crf") + 1] == "20"
    assert process_args[process_args.index("-c:a") + 1] == "libopus"
    assert process_args[process_args.index("-ar") + 1] == "48000"
    assert process_args[process_args.index("-ac") + 1] == "2"
    assert process_args[-1].endswith("prep_0.mp4")


def test_single_processed_clip_compose_uses_processed_file():
    tl = make_timeline()
    tl.find_clip("c1").speed = 2.0
    recorded = {"calls": [], "concat": None}
    exporter = NativeExporter()
    with mock.patch("gui.video_edit.exporter.run_ffmpeg", side_effect=make_fake_ffmpeg(recorded)):
        data = exporter.export(tl, {"format": "mp4"})
    assert data == b"fake-video-bytes"
    assert len(recorded["calls"]) == 2
    compose_args = recorded["calls"][1]
    assert compose_args[:2] == ["-i", compose_args[1]]
    assert compose_args[1].endswith("prep_0.mp4")
    assert compose_args[2:4] == ["-c", "copy"]


def test_multi_clip_concat_uses_processed_files():
    tl = TimelineModel(id="tl1", name="测试")
    t1 = Track(id="t1", type="video", name="视频轨")
    t1.add_clip(
        Clip(id="c1", source_file="a.mp4", timeline_in=0, source_in=0, source_out=5, speed=2.0)
    )
    t1.add_clip(
        Clip(id="c2", source_file="b.mp4", timeline_in=5, source_in=1, source_out=4, speed=2.0)
    )
    tl.add_track(t1)
    recorded = {"calls": [], "concat": None}
    exporter = NativeExporter()
    with mock.patch("gui.video_edit.exporter.run_ffmpeg", side_effect=make_fake_ffmpeg(recorded)):
        data = exporter.export(tl, {"format": "mp4"})
    assert data == b"fake-video-bytes"
    assert len(recorded["calls"]) == 3
    assert recorded["calls"][0][1:5] == ["a.mp4", "-ss", "0", "-t"]
    assert recorded["calls"][1][1:5] == ["b.mp4", "-ss", "1", "-t"]
    assert "setpts=PTS/2.0" in recorded["calls"][0][7]
    assert "setpts=PTS/2.0" in recorded["calls"][1][7]
    lines = recorded["concat"].strip().splitlines()
    assert len(lines) == 2
    assert "prep_0.mp4" in lines[0]
    assert "prep_1.mp4" in lines[1]
    assert "a.mp4" not in recorded["concat"]
    assert "b.mp4" not in recorded["concat"]
    compose_args = recorded["calls"][2]
    assert compose_args[:4] == ["-f", "concat", "-safe", "0"]
