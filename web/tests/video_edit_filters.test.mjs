import test from "node:test";
import assert from "node:assert/strict";
import { Clip, createDefaultParams } from "../lib/video_edit/model.js";
import { buildClipFilter, needsProcessing } from "../lib/video_edit/filters.js";

test("buildClipFilter: 无参数时返回 copy 滤镜", () => {
  const clip = new Clip({ sourceFile: "a.mp4", params: createDefaultParams() });
  const f = buildClipFilter(clip, 0, 0);
  assert.match(f, /copy\[v0\]/);
});

test("buildClipFilter: 裁剪生成 crop 滤镜", () => {
  const params = createDefaultParams();
  params.transform.crop = { x: 100, y: 50, width: 640, height: 480 };
  const clip = new Clip({ sourceFile: "a.mp4", params });
  const f = buildClipFilter(clip, 0, 0);
  assert.match(f, /crop=640:480:100:50/);
});

test("buildClipFilter: 缩放生成 scale 滤镜", () => {
  const params = createDefaultParams();
  params.transform.scale = 0.5;
  const clip = new Clip({ sourceFile: "a.mp4", params });
  const f = buildClipFilter(clip, 0, 0);
  assert.match(f, /scale=iw\*0\.5:ih\*0\.5/);
});

test("buildClipFilter: 旋转 90 度生成 transpose=1", () => {
  const params = createDefaultParams();
  params.transform.rotation = 90;
  const clip = new Clip({ sourceFile: "a.mp4", params });
  const f = buildClipFilter(clip, 0, 0);
  assert.match(f, /transpose=1/);
});

test("buildClipFilter: 翻转生成 hflip/vflip", () => {
  const params = createDefaultParams();
  params.transform.flipH = true;
  params.transform.flipV = true;
  const clip = new Clip({ sourceFile: "a.mp4", params });
  const f = buildClipFilter(clip, 0, 0);
  assert.match(f, /hflip/);
  assert.match(f, /vflip/);
});

test("buildClipFilter: 速度生成 setpts", () => {
  const clip = new Clip({ sourceFile: "a.mp4", speed: 2.0, params: createDefaultParams() });
  const f = buildClipFilter(clip, 0, 0);
  assert.match(f, /setpts=PTS\/2/);
});

test("buildClipFilter: 亮度调整", () => {
  const params = createDefaultParams();
  params.filters.brightness = 0.2;
  const clip = new Clip({ sourceFile: "a.mp4", params });
  const f = buildClipFilter(clip, 0, 0);
  assert.match(f, /brightness=0\.2/);
});

test("buildClipFilter: 对比度调整", () => {
  const params = createDefaultParams();
  params.filters.contrast = 0.3;
  const clip = new Clip({ sourceFile: "a.mp4", params });
  const f = buildClipFilter(clip, 0, 0);
  assert.match(f, /contrast=1\.3/);
});

test("buildClipFilter: 灰度", () => {
  const params = createDefaultParams();
  params.filters.grayscale = true;
  const clip = new Clip({ sourceFile: "a.mp4", params });
  const f = buildClipFilter(clip, 0, 0);
  assert.match(f, /format=gray/);
});

test("buildClipFilter: 文字叠加", () => {
  const params = createDefaultParams();
  params.overlay = { type: "text", text: "Hello", fontSize: 24, fontColor: "white", position: { x: 50, y: 50 }, opacity: 1 };
  const clip = new Clip({ sourceFile: "a.mp4", params });
  const f = buildClipFilter(clip, 0, 0);
  assert.match(f, /drawtext/);
  assert.match(f, /text='Hello'/);
});

test("buildClipFilter: 模糊", () => {
  const params = createDefaultParams();
  params.filters.blur = 2;
  const clip = new Clip({ sourceFile: "a.mp4", params });
  const f = buildClipFilter(clip, 0, 0);
  assert.match(f, /gblur=sigma=2/);
});

test("buildClipFilter: 锐化", () => {
  const params = createDefaultParams();
  params.filters.sharpen = 1.5;
  const clip = new Clip({ sourceFile: "a.mp4", params });
  const f = buildClipFilter(clip, 0, 0);
  assert.match(f, /unsharp=5:5:1\.5/);
});

test("needsProcessing: 默认参数不需要预处理", () => {
  const clip = new Clip({ sourceFile: "a.mp4", params: createDefaultParams() });
  assert.equal(needsProcessing(clip), false);
});

test("needsProcessing: 任何参数变化都需要预处理", () => {
  const clip = new Clip({ sourceFile: "a.mp4", speed: 1.5, params: createDefaultParams() });
  assert.equal(needsProcessing(clip), true);
});
