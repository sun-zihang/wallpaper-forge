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

function withVideoProbeEnv(t, video, { dropObjectUrl = false } = {}) {
  const origCreate = globalThis.document;
  const origUrlCreate = URL.createObjectURL;
  const origUrlRevoke = URL.revokeObjectURL;
  const origSetTimeout = globalThis.setTimeout;
  const state = { revoked: [], timeouts: [] };
  globalThis.document = {
    createElement(tag) {
      assert.equal(tag, "video");
      return video;
    },
  };
  if (dropObjectUrl) {
    try {
      delete URL.createObjectURL;
    } catch {
      URL.createObjectURL = undefined;
    }
  } else {
    URL.createObjectURL = () => "blob:probe";
    URL.revokeObjectURL = (u) => state.revoked.push(u);
  }
  globalThis.setTimeout = (fn, ms) => {
    state.timeouts.push(ms);
    const h = setImmediate(fn);
    return h;
  };
  t.after(() => {
    globalThis.document = origCreate;
    globalThis.setTimeout = origSetTimeout;
    if (dropObjectUrl) {
      URL.createObjectURL = origUrlCreate;
    } else {
      URL.createObjectURL = origUrlCreate;
      URL.revokeObjectURL = origUrlRevoke;
    }
  });
  return state;
}

function makeVideo(duration) {
  return {
    preload: "",
    duration,
    attrs: { src: "blob:probe" },
    onloadedmetadata: null,
    onerror: null,
    removeAttribute(k) {
      delete this.attrs[k];
    },
    load() {
      this.loaded = true;
    },
  };
}

test("probeVideoDuration resolves the finite duration and cleans up", async (t) => {
  const video = makeVideo(12.5);
  const state = withVideoProbeEnv(t, video);
  const p = probeVideoDuration({ name: "a.mp4" });
  const handler = video.onloadedmetadata;
  handler();
  handler(); // settled guard: second call is a no-op
  assert.equal(await p, 12.5);
  assert.equal(video.attrs.src, undefined);
  assert.equal(video.loaded, true);
  assert.deepEqual(state.revoked, ["blob:probe"]);
  assert.equal(video.onloadedmetadata, null);
  assert.equal(video.onerror, null);
});

test("probeVideoDuration maps non-finite or empty durations to null", async (t) => {
  for (const bad of [Infinity, NaN, 0, -1]) {
    const video = makeVideo(bad);
    withVideoProbeEnv(t, video);
    const p = probeVideoDuration({ name: "a.mp4" });
    video.onloadedmetadata();
    assert.equal(await p, null, `duration ${bad} → null`);
    video.onerror = null;
    video.onloadedmetadata = null;
    video.attrs = { src: "blob:probe" };
  }
});

test("probeVideoDuration resolves null on video error", async (t) => {
  const video = makeVideo(10);
  withVideoProbeEnv(t, video);
  const p = probeVideoDuration({ name: "a.mp4" });
  video.onerror();
  assert.equal(await p, null);
});

test("probeVideoDuration gives up after the 5s timeout", async (t) => {
  const video = makeVideo(10);
  const state = withVideoProbeEnv(t, video);
  const p = probeVideoDuration({ name: "a.mp4" });
  assert.equal(await p, null);
  assert.deepEqual(state.timeouts, [5000]);
});

test("probeVideoDuration resolves null when URL.createObjectURL is absent", async (t) => {
  const video = makeVideo(10);
  withVideoProbeEnv(t, video, { dropObjectUrl: true });
  assert.equal(await probeVideoDuration({ name: "a.mp4" }), null);
});
