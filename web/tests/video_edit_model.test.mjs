import test from "node:test";
import assert from "node:assert/strict";
import { TimelineModel, Track, Clip, createDefaultParams } from "../lib/video_edit/model.js";

function makeClip(overrides = {}) {
  return new Clip({
    id: "c1",
    sourceFile: "test.mp4",
    timelineIn: 0,
    sourceIn: 0,
    sourceOut: 5,
    speed: 1.0,
    params: createDefaultParams(),
    ...overrides,
  });
}

test("Clip: duration 计算为 (sourceOut - sourceIn) / speed", () => {
  const clip = makeClip({ sourceIn: 0, sourceOut: 10, speed: 2.0 });
  assert.equal(clip.duration, 5);
});

test("Clip: duration speed=1 时等于源长度", () => {
  const clip = makeClip({ sourceIn: 2, sourceOut: 7, speed: 1.0 });
  assert.equal(clip.duration, 5);
});

test("Clip: splitAt 在时间点拆分片段", () => {
  const clip = makeClip({ sourceIn: 0, sourceOut: 10, speed: 1.0 });
  const [c1, c2] = clip.splitAt(4);
  assert.equal(c1.sourceIn, 0);
  assert.equal(c1.sourceOut, 4);
  assert.equal(c2.sourceIn, 4);
  assert.equal(c2.sourceOut, 10);
  assert.equal(c1.duration + c2.duration, clip.duration);
});

test("Clip: splitAt 考虑速度", () => {
  const clip = makeClip({ sourceIn: 0, sourceOut: 10, speed: 2.0 });
  const [c1, c2] = clip.splitAt(3);
  assert.equal(c1.sourceOut, 6);
  assert.equal(c2.sourceIn, 6);
  assert.equal(c1.duration + c2.duration, clip.duration);
});

test("Track: addClip 和 removeClip", () => {
  const track = new Track({ id: "t1", type: "video", name: "视频轨" });
  const clip = makeClip();
  track.addClip(clip);
  assert.equal(track.clips.length, 1);
  track.removeClip("c1");
  assert.equal(track.clips.length, 0);
});

test("Track: replaceClip 用新片段替换旧片段", () => {
  const track = new Track({ id: "t1", type: "video", name: "视频轨" });
  const clip = makeClip();
  track.addClip(clip);
  const [c1, c2] = clip.splitAt(3);
  track.replaceClip("c1", [c1, c2]);
  assert.equal(track.clips.length, 2);
});

test("TimelineModel: duration 为所有轨道最大结束时间", () => {
  const tl = new TimelineModel({ id: "tl1", name: "测试" });
  const track = new Track({ id: "t1", type: "video", name: "视频轨" });
  track.addClip(makeClip({ timelineIn: 0, sourceOut: 5 }));
  track.addClip(makeClip({ id: "c2", timelineIn: 5, sourceIn: 0, sourceOut: 8 }));
  tl.addTrack(track);
  assert.equal(tl.duration, 13);
});

test("TimelineModel: findClip 跨轨道查找", () => {
  const tl = new TimelineModel({ id: "tl1", name: "测试" });
  const track1 = new Track({ id: "t1", type: "video", name: "视频轨" });
  const track2 = new Track({ id: "t2", type: "audio", name: "音频轨" });
  track1.addClip(makeClip({ id: "c1" }));
  track2.addClip(makeClip({ id: "c2" }));
  tl.addTrack(track1);
  tl.addTrack(track2);
  assert.equal(tl.findClip("c2").id, "c2");
  assert.equal(tl.getClipTrack("c2").id, "t2");
});

test("TimelineModel: 序列化与反序列化", () => {
  const tl = new TimelineModel({ id: "tl1", name: "测试" });
  const track = new Track({ id: "t1", type: "video", name: "视频轨" });
  track.addClip(makeClip({ id: "c1", timelineIn: 2, sourceIn: 1, sourceOut: 6, speed: 1.5 }));
  tl.addTrack(track);
  const json = JSON.parse(JSON.stringify(tl.toJSON()));
  const tl2 = TimelineModel.fromJSON(json);
  assert.equal(tl2.duration, tl.duration);
  assert.equal(tl2.findClip("c1").sourceIn, 1);
  assert.equal(tl2.findClip("c1").speed, 1.5);
});

test("createDefaultParams: 返回完整默认参数", () => {
  const p = createDefaultParams();
  assert.equal(p.transform.rotation, 0);
  assert.equal(p.transform.flipH, false);
  assert.equal(p.transform.scale, 1.0);
  assert.equal(p.transform.crop, null);
  assert.equal(p.audio.volume, 1.0);
  assert.equal(p.audio.fadeIn, 0);
  assert.equal(p.audio.fadeOut, 0);
  assert.equal(p.overlay, null);
  assert.equal(p.filters.brightness, 0);
  assert.equal(p.filters.contrast, 0);
  assert.equal(p.filters.grayscale, false);
});
