// web/tests/video_limits.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  assertVideoLimits,
  durationTooLongError,
  probeVideoDuration,
  MAX_VIDEO_BYTES,
  MAX_VIDEO_SECONDS,
} from "../lib/video_limits.js";

test("limits constants", () => {
  assert.equal(MAX_VIDEO_BYTES, 100 * 1024 * 1024);
  assert.equal(MAX_VIDEO_SECONDS, 300);
});

test("assert rejects oversize", () => {
  assert.throws(() => assertVideoLimits({ name: "a.mp4", size: MAX_VIDEO_BYTES + 1 }), /桌面/);
  assert.throws(() => assertVideoLimits({ name: "a.mp4", size: 100, durationSec: MAX_VIDEO_SECONDS + 1 }), /桌面/);
  assert.doesNotThrow(() => assertVideoLimits({ name: "a.mp4", size: 100, durationSec: 1 }));
});

test("assert tolerates missing size and duration", () => {
  assert.doesNotThrow(() => assertVideoLimits({ name: "a.mp4" }));
  assert.doesNotThrow(() => assertVideoLimits({ name: "a.mp4", size: 10, durationSec: null }));
  assert.doesNotThrow(() => assertVideoLimits({ name: "a.mp4", size: 0, durationSec: 0 }));
  // non-finite duration must not throw (NaN > MAX is false)
  assert.doesNotThrow(() => assertVideoLimits({ size: 1, durationSec: NaN }));
  assert.doesNotThrow(() => assertVideoLimits({ size: 1, durationSec: undefined }));
});

test("assert rejects exactly MAX_VIDEO_BYTES+1 but allows MAX", () => {
  assert.throws(() => assertVideoLimits({ size: MAX_VIDEO_BYTES + 1 }), /100MB/);
  assert.doesNotThrow(() => assertVideoLimits({ size: MAX_VIDEO_BYTES }));
  assert.throws(() => assertVideoLimits({ size: 1, durationSec: MAX_VIDEO_SECONDS + 1 }), /300 秒/);
  assert.doesNotThrow(() => assertVideoLimits({ size: 1, durationSec: MAX_VIDEO_SECONDS }));
});

test("durationTooLongError carries the 300s message", () => {
  const e = durationTooLongError();
  assert.equal(e.label, "视频处理失败");
  assert.match(e.detail, /300 秒/);
  assert.match(e.detail, /桌面/);
});

test("probeVideoDuration resolves null when document/url unavailable", async () => {
  assert.equal(await probeVideoDuration({ name: "a.mp4" }), null);
});
