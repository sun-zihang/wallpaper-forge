// web/tests/video_limits.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { assertVideoLimits, MAX_VIDEO_BYTES, MAX_VIDEO_SECONDS } from "../lib/video_limits.js";

test("limits constants", () => {
  assert.equal(MAX_VIDEO_BYTES, 100 * 1024 * 1024);
  assert.equal(MAX_VIDEO_SECONDS, 300);
});

test("assert rejects oversize", () => {
  assert.throws(() => assertVideoLimits({ name: "a.mp4", size: MAX_VIDEO_BYTES + 1 }), /桌面/);
  assert.throws(() => assertVideoLimits({ name: "a.mp4", size: 100, durationSec: MAX_VIDEO_SECONDS + 1 }), /桌面/);
  assert.doesNotThrow(() => assertVideoLimits({ name: "a.mp4", size: 100, durationSec: 1 }));
});
