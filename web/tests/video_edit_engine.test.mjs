// web/tests/video_edit_engine.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { TimelineModel, Track, Clip, createDefaultParams } from "../lib/video_edit/model.js";
import { EditEngine, SplitClipCommand, RemoveClipCommand, MoveClipCommand, AdjustParamsCommand } from "../lib/video_edit/engine.js";

function makeTimeline() {
  const tl = new TimelineModel({ id: "tl1" });
  const track = new Track({ id: "t1", type: "video", name: "视频轨" });
  track.addClip(new Clip({ id: "c1", sourceFile: "a.mp4", timelineIn: 0, sourceIn: 0, sourceOut: 10, speed: 1, params: createDefaultParams() }));
  track.addClip(new Clip({ id: "c2", sourceFile: "b.mp4", timelineIn: 10, sourceIn: 0, sourceOut: 5, speed: 1, params: createDefaultParams() }));
  tl.addTrack(track);
  return tl;
}

test("EditEngine: split 片段产生两个片段", () => {
  const tl = makeTimeline();
  const engine = new EditEngine(tl);
  engine.execute(new SplitClipCommand("c1", 4));
  const track = tl.getClipTrack("c1");
  assert.equal(track.clips.length, 3);
  assert.equal(tl.findClip("c1").sourceOut, 4);
  const newClip = track.clips.find((c) => c.id !== "c1" && c.id !== "c2");
  assert.ok(newClip);
  assert.equal(newClip.sourceIn, 4);
  assert.equal(newClip.sourceOut, 10);
});

test("EditEngine: undo 恢复 split 前状态", () => {
  const tl = makeTimeline();
  const engine = new EditEngine(tl);
  engine.execute(new SplitClipCommand("c1", 4));
  engine.undo();
  const track = tl.getClipTrack("c1");
  assert.equal(track.clips.length, 2);
  assert.equal(tl.findClip("c1").sourceOut, 10);
});

test("EditEngine: redo 重新应用 split", () => {
  const tl = makeTimeline();
  const engine = new EditEngine(tl);
  engine.execute(new SplitClipCommand("c1", 4));
  engine.undo();
  engine.redo();
  assert.equal(tl.getClipTrack("c1").clips.length, 3);
});

test("EditEngine: undo 栈深度限制为 50", () => {
  const tl = makeTimeline();
  const engine = new EditEngine(tl);
  for (let i = 0; i < 60; i++) {
    engine.execute(new AdjustParamsCommand("c1", { filters: { brightness: i * 0.01 } }));
  }
  assert.equal(engine.undoStack.length, 50);
});

test("EditEngine: execute 清空 redo 栈", () => {
  const tl = makeTimeline();
  const engine = new EditEngine(tl);
  engine.execute(new SplitClipCommand("c1", 4));
  engine.undo();
  assert.equal(engine.redoStack.length, 1);
  engine.execute(new SplitClipCommand("c1", 2));
  assert.equal(engine.redoStack.length, 0);
});

test("EditEngine: remove 和 undo remove", () => {
  const tl = makeTimeline();
  const engine = new EditEngine(tl);
  engine.execute(new RemoveClipCommand("c1"));
  assert.equal(tl.findClip("c1"), null);
  engine.undo();
  assert.ok(tl.findClip("c1"));
});

test("EditEngine: move 片段到新位置", () => {
  const tl = makeTimeline();
  const engine = new EditEngine(tl);
  engine.execute(new MoveClipCommand("c1", "t1", 20));
  assert.equal(tl.findClip("c1").timelineIn, 20);
  engine.undo();
  assert.equal(tl.findClip("c1").timelineIn, 0);
});

test("EditEngine: adjustParams 更新片段参数", () => {
  const tl = makeTimeline();
  const engine = new EditEngine(tl);
  engine.execute(new AdjustParamsCommand("c1", { speed: 2.0 }));
  assert.equal(tl.findClip("c1").speed, 2.0);
  engine.undo();
  assert.equal(tl.findClip("c1").speed, 1.0);
});
