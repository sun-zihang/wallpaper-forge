import test from "node:test";
import assert from "node:assert/strict";

function installStorage() {
  const store = new Map();
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
  };
  return store;
}

test("getStats returns zeros before anything is tracked", async () => {
  installStorage();
  const { getStats } = await import("../lib/track.js");
  const s = getStats();
  assert.equal(s.total, 0);
  assert.equal(s.added, 0);
  assert.equal(s.starts, 0);
  assert.equal(s.avgMs, 0);
  assert.equal(s.abandonRate, 0);
  assert.equal(s.uploadsNotStarted, 0);
  assert.deepEqual(s.recent, []);
  assert.deepEqual(s.modules, {});
});

test("bump accumulates counters across calls", async () => {
  installStorage();
  const { bump, getStats } = await import("../lib/track.js");
  bump("module:gif");
  bump("module:gif");
  bump("module:image");
  const s = getStats();
  assert.equal(s.counters["module:gif"], 2);
  assert.equal(s.counters["module:image"], 1);
  assert.equal(s.total, 3);
  assert.deepEqual(s.modules, { gif: 2, image: 1 });
});

test("track records bounded recent events with detail", async () => {
  installStorage();
  const { track, getStats } = await import("../lib/track.js");
  for (let i = 0; i < 250; i++) track("files_added", { n: i });
  const s = getStats();
  assert.equal(s.counters.files_added, 250, "counter keeps every event");
  assert.equal(s.recent.length, 20, "recent view capped at 20");
  assert.equal(s.recent[0].name, "files_added");
  assert.ok(typeof s.recent[0].t === "number");
});

test("failure buckets land in the failures distribution", async () => {
  installStorage();
  const { trackFailure, getStats } = await import("../lib/track.js");
  trackFailure(new Error("文件头无法识别为图片"));
  trackFailure(new Error("文件头无法识别为图片"));
  trackFailure(new Error("视频引擎加载失败"));
  const s = getStats();
  assert.equal(s.failures.corrupt, 2);
  assert.equal(s.failures.engine, 1);
});

test("module and desktop helpers key correctly", async () => {
  installStorage();
  const { trackModule, trackDesktop, getStats } = await import("../lib/track.js");
  trackModule("/");
  trackModule("/video");
  trackDesktop("download");
  trackDesktop("footer");
  const s = getStats();
  assert.equal(s.modules.home, 1);
  assert.equal(s.modules.video, 1);
  assert.equal(s.desktop, 2);
  assert.equal(s.recent[0].action, "footer");
});

test("funnel and average derive from counters", async () => {
  installStorage();
  const { trackUpload, trackStart, trackEnd, bump, getStats } = await import("../lib/track.js");
  trackUpload(3);
  trackUpload(2);
  trackStart();
  trackEnd(Date.now() - 1000);
  const s = getStats();
  assert.equal(s.added, 2);
  assert.equal(s.starts, 1);
  assert.equal(s.uploadsNotStarted, 0.5, "1 of 2 uploads never started");
  assert.equal(s.runs, 1);
  assert.ok(s.avgMs >= 1000, "avg reflects the recorded duration");
  assert.equal(s.abandonRate, 0, "no abandonment recorded");
  bump("abandoned");
  assert.equal(getStats().abandonRate, 1, "1 abandoned of 1 start");
});

test("upload-not-started rate clamps to 0..1", async () => {
  installStorage();
  const { trackStart, getStats } = await import("../lib/track.js");
  trackStart();
  trackStart();
  trackStart();
  const s = getStats();
  assert.equal(s.uploadsNotStarted, 0, "starts without uploads cannot go negative");
});

test("clearStats wipes everything", async () => {
  installStorage();
  const { track, clearStats, getStats } = await import("../lib/track.js");
  track("files_added", { n: 1 });
  assert.ok(getStats().total > 0);
  clearStats();
  const s = getStats();
  assert.equal(s.total, 0);
  assert.deepEqual(s.recent, []);
});

test("storage failures degrade to no-ops", async () => {
  globalThis.localStorage = {
    getItem: () => {
      throw new Error("denied");
    },
    setItem: () => {
      throw new Error("denied");
    },
    removeItem: () => {
      throw new Error("denied");
    },
  };
  const { bump, track, trackFailure, getStats, clearStats } = await import("../lib/track.js");
  assert.doesNotThrow(() => bump("x"));
  assert.doesNotThrow(() => track("y", { a: 1 }));
  assert.doesNotThrow(() => trackFailure(new Error("boom")));
  assert.doesNotThrow(clearStats);
  assert.equal(getStats().total, 0);
});

test("corrupted payload falls back to a fresh view", async () => {
  const store = new Map([["wc.track.v1", "{not json"]]);
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
  };
  const { bump, getStats } = await import("../lib/track.js");
  bump("module:home");
  assert.equal(getStats().modules.home, 1, "recovers from corrupt storage");
});
