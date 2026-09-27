// web/tests/memory.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { createMemoryMonitor } from "../lib/memory.js";

test("createMemoryMonitor is a no-op without performance.memory", () => {
  const origPerf = globalThis.performance;
  globalThis.performance = {};
  try {
    const m = createMemoryMonitor({ onWarning: () => assert.fail("must not warn") });
    assert.equal(m.usageMb, null);
    m.stop();
    m.stop(); // idempotent
  } finally {
    globalThis.performance = origPerf;
  }
});

test("createMemoryMonitor reports usage and warns past the limit", async () => {
  const origPerf = globalThis.performance;
  const warnings = [];
  globalThis.performance = {
    memory: { usedJSHeapSize: 2048 * 1024 * 1024 },
  };
  const origSetInterval = globalThis.setInterval;
  const origClearInterval = globalThis.clearInterval;
  let tick = null;
  globalThis.setInterval = (fn) => {
    tick = fn;
    return 42;
  };
  globalThis.clearInterval = (id) => {
    assert.equal(id, 42);
  };
  try {
    const m = createMemoryMonitor({ intervalMs: 5, limitMb: 1500, onWarning: (mb) => warnings.push(mb) });
    assert.equal(Math.round(m.usageMb), 2048);
    assert.equal(warnings.length, 0, "no warning before the interval fires");
    tick();
    assert.equal(warnings.length, 1);
    assert.equal(Math.round(warnings[0]), 2048);
    m.stop();
  } finally {
    globalThis.performance = origPerf;
    globalThis.setInterval = origSetInterval;
    globalThis.clearInterval = origClearInterval;
  }
});

test("createMemoryMonitor stays silent below the limit", () => {
  const origPerf = globalThis.performance;
  globalThis.performance = { memory: { usedJSHeapSize: 100 * 1024 * 1024 } };
  const origSetInterval = globalThis.setInterval;
  let tick = null;
  globalThis.setInterval = (fn) => {
    tick = fn;
    return 1;
  };
  try {
    const m = createMemoryMonitor({ limitMb: 1500, onWarning: () => assert.fail("must not warn") });
    tick();
    m.stop();
  } finally {
    globalThis.performance = origPerf;
    globalThis.setInterval = origSetInterval;
  }
});
