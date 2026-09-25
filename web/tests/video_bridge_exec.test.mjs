// web/tests/video_bridge_exec.test.mjs
// runFFmpeg execution paths with a rich fake FFmpeg instance (fresh module
// state per file: node --test runs each file in its own process).
import test from "node:test";
import assert from "node:assert/strict";
import { ensureFFmpeg, runFFmpeg } from "../lib/video_bridge.js";

const hub = {
  scriptMode: "ok",
  scripts: [],
  execImpl: null,
  instance: null,
  terminated: 0,
};

globalThis.document = {
  createElement() {
    const el = { onload: null, onerror: null };
    Object.defineProperty(el, "src", {
      set(value) {
        hub.scripts.push(value);
        queueMicrotask(() => {
          if (hub.scriptMode === "error") {
            if (el.onerror) el.onerror();
          } else if (el.onload) {
            el.onload();
          }
        });
      },
    });
    return el;
  },
  head: { appendChild() {} },
};

globalThis.FFmpegUtil = {
  async toBlobURL(url) {
    return `blob:${url}`;
  },
};

globalThis.FFmpegWASM = {
  FFmpeg: class {
    constructor() {
      this.handlers = new Map();
      this.execCalls = [];
      this.offCalls = [];
      hub.instance = this;
    }
    async load(args) {
      this.loadArgs = args;
    }
    on(event, fn) {
      this.handlers.set(event, fn);
      return () => this.handlers.delete(event);
    }
    off(event, fn) {
      this.offCalls.push(event);
      if (this.handlers.get(event) === fn) this.handlers.delete(event);
    }
    async exec(args) {
      this.execCalls.push(args);
      if (hub.execImpl) return hub.execImpl(this);
      return 0;
    }
    async terminate() {
      hub.terminated += 1;
      return 0;
    }
    emit(event, payload) {
      const fn = this.handlers.get(event);
      if (fn) fn(payload);
    }
  },
};

test("ensureFFmpeg failure is wrapped as AppError and retryable", async () => {
  hub.scriptMode = "error";
  await assert.rejects(() => ensureFFmpeg(), (e) => {
    assert.equal(e.label, "视频处理失败");
    assert.match(e.detail, /all mirrors failed/);
    return true;
  });
  // loadPromise reset → a later call with healthy mirrors succeeds
  hub.scriptMode = "ok";
  const inst = await ensureFFmpeg();
  assert.ok(inst);
  assert.equal(hub.instance, inst);
});

test("ensureFFmpeg reports status milestones and wires load()", async () => {
  // already cached by the previous test → returns immediately
  const statuses = [];
  const again = await ensureFFmpeg((s) => statuses.push(s));
  assert.equal(again, hub.instance);
  assert.deepEqual(statuses, []);
  assert.ok(hub.instance.loadArgs.classWorkerURL.startsWith("blob:"));
});

test("runFFmpeg drives progress, logs, and unsubscribes on success", async () => {
  const inst = hub.instance;
  const seen = [];
  const token = undefined;
  await runFFmpeg({
    args: ["-i", "in.mp4", "out.mp4"],
    outPath: "out.mp4",
    onProgress: (p, s) => seen.push([p, s]),
    cancelToken: token,
  });
  assert.deepEqual(inst.execCalls[0], ["-i", "in.mp4", "out.mp4"]);

  inst.emit("progress", { progress: 0.5 });
  inst.emit("progress", { progress: null });
  inst.emit("progress", { progress: 2 });
  inst.emit("progress", { progress: -1 });
  inst.emit("log", { message: "frame=42" });
  inst.emit("log", { message: "" });
  inst.emit("log", { message: 123 });
  // handlers were unsubscribed inside runFFmpeg's finally
  assert.equal(inst.handlers.has("progress"), false);
  assert.equal(inst.handlers.has("log"), false);
  // late events after unsubscribe are ignored
  inst.emit("progress", { progress: 0.9 });

  const plain = seen.filter(([, s]) => s == null);
  assert.ok(plain.some(([p]) => p === 100), "final 100 reported");
  // clamped values arrived before unsubscribe
  assert.deepEqual(
    seen.filter(([p, s]) => s == null && p !== 100).map(([p]) => p),
    [],
  );
});

test("runFFmpeg reports clamped progress events from the instance", async () => {
  const inst = hub.instance;
  const seen = [];
  // re-subscribe happens inside runFFmpeg; collect events during the run
  const origExec = inst.exec.bind(inst);
  inst.exec = async (args) => {
    inst.emit("progress", { progress: 0.5 });
    inst.emit("progress", { progress: null });
    inst.emit("progress", { progress: 2 });
    inst.emit("progress", { progress: -1 });
    inst.emit("log", { message: "frame=1" });
    inst.emit("log", { message: "" });
    inst.emit("log", { message: 7 });
    inst.emit("progress", { progress: 0.49 });
    return origExec(args);
  };
  try {
    await runFFmpeg({
      args: ["x"],
      outPath: "y",
      onProgress: (p, s) => seen.push([p, s]),
    });
  } finally {
    inst.exec = origExec;
  }
  const values = seen.filter(([, s]) => s == null).map(([p]) => p);
  assert.deepEqual(values, [50, 100, 0, 49, 100]);
});

test("runFFmpeg with pre-cancelled token throws before exec", async () => {
  const inst = hub.instance;
  const before = inst.execCalls.length;
  await assert.rejects(
    () =>
      runFFmpeg({
        args: ["x"],
        outPath: "y",
        cancelToken: { cancelled: true },
      }),
    (e) => {
      assert.equal(e.label, "视频处理失败");
      assert.equal(e.detail, "已取消");
      return true;
    },
  );
  assert.equal(inst.execCalls.length, before);
});

test("runFFmpeg maps exec failure to AppError with log tail", async () => {
  const inst = hub.instance;
  hub.execImpl = (self) => {
    self.emit("log", { message: "line-α" });
    self.emit("log", { message: "line-β" });
    throw new Error("boom");
  };
  try {
    await assert.rejects(
      () => runFFmpeg({ args: ["x"], outPath: "y" }),
      (e) => {
        assert.equal(e.label, "视频处理失败");
        assert.match(e.detail, /boom/);
        assert.match(e.detail, /line-β/);
        return true;
      },
    );
  } finally {
    hub.execImpl = null;
  }
});

test("runFFmpeg cancelled during exec reports 已取消", async () => {
  const token = { cancelled: false };
  hub.execImpl = (self) => {
    token.cancelled = true;
    self.emit("log", { message: "partial" });
    throw new Error("interrupted");
  };
  try {
    await assert.rejects(
      () => runFFmpeg({ args: ["x"], outPath: "y", cancelToken: token }),
      (e) => {
        assert.equal(e.detail, "已取消");
        return true;
      },
    );
  } finally {
    hub.execImpl = null;
  }
});

test("runFFmpeg cancelled after successful exec still throws", async () => {
  const token = { cancelled: false };
  hub.execImpl = () => {
    token.cancelled = true;
    return 0;
  };
  try {
    await assert.rejects(
      () => runFFmpeg({ args: ["x"], outPath: "y", cancelToken: token }),
      (e) => {
        assert.equal(e.detail, "已取消");
        return true;
      },
    );
  } finally {
    hub.execImpl = null;
  }
});

test("runFFmpeg non-zero exit surfaces code and log tail", async () => {
  hub.execImpl = (self) => {
    self.emit("log", { message: "encoder exploded" });
    return 5;
  };
  try {
    await assert.rejects(
      () => runFFmpeg({ args: ["x"], outPath: "y" }),
      (e) => {
        assert.equal(e.label, "视频处理失败");
        assert.match(e.detail, /code 5/);
        assert.match(e.detail, /encoder exploded/);
        return true;
      },
    );
  } finally {
    hub.execImpl = null;
  }
});

test("runFFmpeg falls back to off() when on() returns nothing", async () => {
  const inst = hub.instance;
  const origOn = inst.on;
  inst.on = () => undefined;
  try {
    await runFFmpeg({ args: ["x"], outPath: "y" });
    assert.ok(inst.offCalls.includes("progress"));
    assert.ok(inst.offCalls.includes("log"));
  } finally {
    inst.on = origOn;
  }
});

test("cancel token polls interval: no-op while live, terminates when set", async () => {
  const inst = hub.instance;
  const origSetInterval = globalThis.setInterval;
  const origClearInterval = globalThis.clearInterval;
  let tick = null;
  globalThis.setInterval = (fn) => {
    tick = fn;
    return 777;
  };
  const cleared = [];
  globalThis.clearInterval = (h) => cleared.push(h);
  const token = { cancelled: false };
  const origExec = inst.exec.bind(inst);
  try {
    inst.exec = async (args) => {
      // tick while still live → early return, nothing terminates
      if (tick) tick();
      token.cancelled = true;
      if (tick) tick();
      return origExec(args);
    };
    await assert.rejects(
      () => runFFmpeg({ args: ["x"], outPath: "y", cancelToken: token }),
      (e) => {
        assert.equal(e.detail, "已取消");
        return true;
      },
    );
  } finally {
    inst.exec = origExec;
    globalThis.setInterval = origSetInterval;
    globalThis.clearInterval = origClearInterval;
  }
  assert.ok(cleared.includes(777));
  // async terminate branch settles after a macrotask
  await new Promise((r) => setImmediate(r));
  assert.ok(hub.terminated >= 1);
});
