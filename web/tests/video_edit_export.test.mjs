// web/tests/video_edit_export.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { TimelineModel, Track, Clip, createDefaultParams } from "../lib/video_edit/model.js";
import { ExportOrchestrator } from "../lib/video_edit/export.js";

function makeAdapter() {
  const files = new Map();
  const ffmpegCalls = [];
  return {
    files,
    ffmpegCalls,
    async runFFmpeg(args, outPath) {
      ffmpegCalls.push({ args, outPath });
      files.set(outPath, new Uint8Array([1, 2, 3]));
    },
    async writeFile(name, content) {
      files.set(name, content);
    },
    async readFile(name) {
      return new Blob([files.get(name)]);
    },
    async deleteFile(name) {
      files.delete(name);
    },
  };
}

function makeTimeline() {
  const tl = new TimelineModel({ id: "tl1" });
  const track = new Track({ id: "t1", type: "video", name: "视频轨" });
  track.addClip(new Clip({ id: "c1", sourceFile: "a.mp4", timelineIn: 0, sourceIn: 0, sourceOut: 5, speed: 1, params: createDefaultParams() }));
  track.addClip(new Clip({ id: "c2", sourceFile: "b.mp4", timelineIn: 5, sourceIn: 0, sourceOut: 5, speed: 1, params: createDefaultParams() }));
  tl.addTrack(track);
  return tl;
}

test("ExportOrchestrator: 无预处理片段时直接 concat", async () => {
  const tl = makeTimeline();
  const adapter = makeAdapter();
  const orch = new ExportOrchestrator(tl, {}, adapter);
  const progressCalls = [];
  const result = await orch.export((pct) => progressCalls.push(pct));
  assert.ok(result.blob);
  assert.ok(orch._buildPlan().clips.every((c) => !c.needsProcessing));
});

test("ExportOrchestrator: 有预处理片段时先处理再合成", async () => {
  const tl = makeTimeline();
  const clip = tl.findClip("c1");
  clip.speed = 2.0;
  const adapter = makeAdapter();
  const orch = new ExportOrchestrator(tl, {}, adapter);
  await orch.export(() => {});
  const preprocessCall = adapter.ffmpegCalls.find((c) => c.outPath === "prep_0.mp4");
  assert.ok(preprocessCall);
  assert.ok(adapter.ffmpegCalls.some((c) => c.outPath === "output.mp4"));
});

test("ExportOrchestrator: 进度报告从 0 到 100", async () => {
  const tl = makeTimeline();
  const adapter = makeAdapter();
  const orch = new ExportOrchestrator(tl, {}, adapter);
  const pcts = [];
  await orch.export((p) => pcts.push(p));
  assert.equal(pcts[0], 0);
  assert.equal(pcts[pcts.length - 1], 100);
});

test("ExportOrchestrator: 取消导出抛出错误", async () => {
  const tl = makeTimeline();
  const adapter = makeAdapter();
  let callCount = 0;
  adapter.runFFmpeg = async () => {
    callCount++;
    orch.cancelled = true;
  };
  const orch = new ExportOrchestrator(tl, {}, adapter);
  orch.cancelled = false;
  await assert.rejects(() => orch.export(() => {}), /已取消/);
});

test("ExportOrchestrator: 导出后清理中间文件", async () => {
  const tl = makeTimeline();
  const clip = tl.findClip("c1");
  clip.speed = 2.0;
  const adapter = makeAdapter();
  const orch = new ExportOrchestrator(tl, {}, adapter);
  await orch.export(() => {});
  assert.equal(adapter.files.has("prep_0.mp4"), false);
  assert.equal(adapter.files.has("output.mp4"), false);
});

test("ExportOrchestrator: 单片段无音频时直接复制", async () => {
  const tl = new TimelineModel({ id: "tl1" });
  const track = new Track({ id: "t1", type: "video", name: "视频轨" });
  track.addClip(new Clip({ id: "c1", sourceFile: "a.mp4", timelineIn: 0, sourceIn: 0, sourceOut: 5, speed: 1, params: createDefaultParams() }));
  tl.addTrack(track);
  const adapter = makeAdapter();
  const orch = new ExportOrchestrator(tl, {}, adapter);
  await orch.export(() => {});
  const composeCall = adapter.ffmpegCalls.find((c) => c.outPath === "output.mp4");
  assert.ok(composeCall);
  assert.match(composeCall.args.join(" "), /-c copy/);
});
