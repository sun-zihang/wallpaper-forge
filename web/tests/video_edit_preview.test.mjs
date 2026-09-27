import test from "node:test";
import assert from "node:assert/strict";
import { TimelineModel, Track, Clip, createDefaultParams } from "../lib/video_edit/model.js";
import { PreviewCalculator } from "../lib/video_edit/preview.js";

function makeTimeline() {
  const tl = new TimelineModel({ id: "tl1" });
  const videoTrack = new Track({ id: "t1", type: "video", name: "视频轨" });
  videoTrack.addClip(new Clip({ id: "v1", sourceFile: "a.mp4", timelineIn: 0, sourceIn: 0, sourceOut: 10, speed: 1, params: createDefaultParams() }));
  const audioTrack = new Track({ id: "t2", type: "audio", name: "音频轨" });
  audioTrack.addClip(new Clip({ id: "a1", sourceFile: "bgm.mp3", timelineIn: 0, sourceIn: 0, sourceOut: 10, speed: 1, params: createDefaultParams() }));
  const overlayTrack = new Track({ id: "t3", type: "overlay", name: "叠加轨" });
  overlayTrack.addClip(new Clip({
    id: "ov1", sourceFile: "", timelineIn: 2, sourceIn: 0, sourceOut: 5, speed: 1,
    params: { ...createDefaultParams(), overlay: { type: "text", text: "Title", fontSize: 24, fontColor: "white", position: { x: 50, y: 50 }, opacity: 1 } },
  }));
  tl.addTrack(videoTrack);
  tl.addTrack(audioTrack);
  tl.addTrack(overlayTrack);
  return tl;
}

test("PreviewCalculator: 时间点 0 返回第一个视频片段", () => {
  const tl = makeTimeline();
  const calc = new PreviewCalculator();
  const frame = calc.getFrameAt(tl, 0);
  assert.equal(frame.videoLayers.length, 1);
  assert.equal(frame.videoLayers[0].clip.id, "v1");
  assert.equal(frame.videoLayers[0].sourceTime, 0);
});

test("PreviewCalculator: 时间点 5 计算正确的源时间", () => {
  const tl = makeTimeline();
  const calc = new PreviewCalculator();
  const frame = calc.getFrameAt(tl, 5);
  assert.equal(frame.videoLayers[0].sourceTime, 5);
});

test("PreviewCalculator: 速度 2x 时源时间 = sourceIn + localT * speed", () => {
  const tl = new TimelineModel({ id: "tl1" });
  const track = new Track({ id: "t1", type: "video", name: "视频轨" });
  track.addClip(new Clip({ id: "v1", sourceFile: "a.mp4", timelineIn: 0, sourceIn: 2, sourceOut: 12, speed: 2, params: createDefaultParams() }));
  tl.addTrack(track);
  const calc = new PreviewCalculator();
  const frame = calc.getFrameAt(tl, 3);
  assert.equal(frame.videoLayers[0].sourceTime, 8); // 2 + 3*2
});

test("PreviewCalculator: 叠加层只在活跃时间范围返回", () => {
  const tl = makeTimeline();
  const calc = new PreviewCalculator();
  const f1 = calc.getFrameAt(tl, 1);
  assert.equal(f1.overlays.length, 0);
  const f2 = calc.getFrameAt(tl, 3);
  assert.equal(f2.overlays.length, 1);
  assert.equal(f2.overlays[0].clip.params.overlay.text, "Title");
});

test("PreviewCalculator: getAudioMixAt 返回活跃音频片段", () => {
  const tl = makeTimeline();
  const calc = new PreviewCalculator();
  const mix = calc.getAudioMixAt(tl, 5);
  assert.equal(mix.length, 1);
  assert.equal(mix[0].clip.id, "a1");
  assert.equal(mix[0].effectiveVolume, 1.0);
});

test("PreviewCalculator: 淡入淡出计算有效音量", () => {
  const tl = new TimelineModel({ id: "tl1" });
  const track = new Track({ id: "t1", type: "audio", name: "音频轨" });
  const params = createDefaultParams();
  params.audio.fadeIn = 2;
  params.audio.fadeOut = 2;
  params.audio.volume = 0.8;
  track.addClip(new Clip({ id: "a1", sourceFile: "bgm.mp3", timelineIn: 0, sourceIn: 0, sourceOut: 10, speed: 1, params }));
  tl.addTrack(track);
  const calc = new PreviewCalculator();
  assert.equal(calc.getAudioMixAt(tl, 0)[0].effectiveVolume, 0);
  assert.ok(Math.abs(calc.getAudioMixAt(tl, 1)[0].effectiveVolume - 0.4) < 0.01);
  assert.ok(Math.abs(calc.getAudioMixAt(tl, 5)[0].effectiveVolume - 0.8) < 0.01);
  assert.ok(Math.abs(calc.getAudioMixAt(tl, 9)[0].effectiveVolume - 0.4) < 0.01);
  assert.equal(calc.getAudioMixAt(tl, 10).length, 0);
});

test("PreviewCalculator: 多个视频层按轨道顺序返回", () => {
  const tl = new TimelineModel({ id: "tl1" });
  const track1 = new Track({ id: "t1", type: "video", name: "视频轨1" });
  const track2 = new Track({ id: "t2", type: "video", name: "视频轨2" });
  track1.addClip(new Clip({ id: "v1", sourceFile: "a.mp4", timelineIn: 0, sourceIn: 0, sourceOut: 10, speed: 1, params: createDefaultParams() }));
  track2.addClip(new Clip({ id: "v2", sourceFile: "b.mp4", timelineIn: 0, sourceIn: 0, sourceOut: 10, speed: 1, params: createDefaultParams() }));
  tl.addTrack(track1);
  tl.addTrack(track2);
  const calc = new PreviewCalculator();
  const frame = calc.getFrameAt(tl, 5);
  assert.equal(frame.videoLayers.length, 2);
});
