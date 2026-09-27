import test from "node:test";
import assert from "node:assert/strict";
import { WorkerPool } from "../lib/worker_pool.js";
import { AppError } from "../lib/errors.js";

class FakeWorker {
  static instances = [];
  constructor(url, opts) {
    this.url = url;
    this.opts = opts;
    this.terminated = false;
    this.sent = [];
    this.failPost = false;
    FakeWorker.instances.push(this);
  }
  postMessage(data, transfer) {
    if (this.failPost) throw new Error("postMessage failed");
    this.sent.push({ data, transfer: transfer || [] });
  }
  terminate() {
    this.terminated = true;
  }
  emit(data) {
    this.onmessage({ data });
  }
  crash(message) {
    this.onerror({ message });
  }
}

function freshPool({ size = 2, Ctor = FakeWorker } = {}) {
  FakeWorker.instances = [];
  return new WorkerPool({ workerUrl: "worker.js", size, WorkerCtor: Ctor, workerOptions: { type: "module" } });
}

test("pool rejects construction without a Worker constructor", () => {
  assert.throws(() => new WorkerPool({ workerUrl: "w.js", WorkerCtor: undefined }), /Worker constructor unavailable/);
});

test("pool spawns a module worker and resolves results", async () => {
  const pool = freshPool();
  const p = pool.run("kind_a", { x: 1 });
  assert.equal(FakeWorker.instances.length, 1);
  const w = FakeWorker.instances[0];
  assert.deepEqual(w.opts, { type: "module" });
  assert.equal(w.sent[0].data.kind, "kind_a");
  assert.deepEqual(w.sent[0].data.payload, { x: 1 });
  w.emit({ id: 1, type: "result", result: { ok: true } });
  assert.deepEqual(await p, { ok: true });
  assert.equal(pool.pending, 0);
});

test("pool forwards the transfer list with the payload", async () => {
  const pool = freshPool();
  const buf = new ArrayBuffer(4);
  const p = pool.run("k", { a: 1 }, { transfer: [buf] });
  assert.deepEqual(FakeWorker.instances[0].sent[0].transfer, [buf]);
  FakeWorker.instances[0].emit({ id: 1, type: "result", result: {} });
  await p;
});

test("pool routes progress then result", async () => {
  const pool = freshPool();
  const seen = [];
  const p = pool.run("k", {}, { onProgress: (d, t) => seen.push([d, t]) });
  const w = FakeWorker.instances[0];
  w.emit({ id: 1, type: "progress", done: 1, total: 4 });
  w.emit({ id: 1, type: "progress", done: 2, total: 4 });
  w.emit({ id: 1, type: "result", result: "done" });
  assert.deepEqual(await p, "done");
  assert.deepEqual(seen, [[1, 4], [2, 4]]);
});

test("pool maps worker errors into AppError with label and detail", async () => {
  const pool = freshPool();
  const p = pool.run("k", {});
  FakeWorker.instances[0].emit({ id: 1, type: "error", label: "GIF 处理失败", detail: "boom" });
  await assert.rejects(() => p, (e) => e instanceof AppError && e.label === "GIF 处理失败" && e.detail === "boom");
});

test("pool queues jobs beyond size and reuses the idle worker", async () => {
  const pool = freshPool({ size: 1 });
  const a = pool.run("a", {});
  const b = pool.run("b", {});
  assert.equal(FakeWorker.instances.length, 1, "second job waits, no extra worker");
  const w = FakeWorker.instances[0];
  w.emit({ id: 1, type: "result", result: 1 });
  assert.deepEqual(await a, 1);
  assert.equal(w.sent.length, 2, "queued job dispatched to the same worker");
  assert.equal(w.sent[1].data.id, 2);
  w.emit({ id: 2, type: "result", result: 2 });
  assert.deepEqual(await b, 2);
});

test("pool rejects the task when dispatch fails, worker stays usable", async () => {
  // dispatch is synchronous inside run(), so the failure is baked into the ctor
  class FailFirstWorker extends FakeWorker {
    postMessage(data, transfer) {
      if (!this._failedOnce) {
        this._failedOnce = true;
        throw new Error("postMessage failed");
      }
      super.postMessage(data, transfer);
    }
  }
  const pool = freshPool({ size: 1, Ctor: FailFirstWorker });
  await assert.rejects(() => pool.run("k", {}), /postMessage failed/);
  const p2 = pool.run("k2", {});
  FakeWorker.instances[0].emit({ id: 2, type: "result", result: "ok" });
  assert.deepEqual(await p2, "ok");
});

test("pool fails the task and respawns after a worker crash", async () => {
  const pool = freshPool({ size: 1 });
  const p = pool.run("k", {}, { label: "图片处理失败" });
  FakeWorker.instances[0].crash("wasm panic");
  await assert.rejects(
    () => p,
    (e) => e instanceof AppError && e.label === "图片处理失败" && /处理线程崩溃: wasm panic/.test(e.detail),
  );
  const p2 = pool.run("k2", {});
  assert.equal(FakeWorker.instances.length, 2, "replacement worker spawned");
  FakeWorker.instances[1].emit({ id: 2, type: "result", result: 7 });
  assert.deepEqual(await p2, 7);
});

test("cancelAll rejects queued and running tasks and tears workers down", async () => {
  const pool = freshPool({ size: 1 });
  const a = pool.run("a", {}, { label: "GIF 处理失败" });
  const b = pool.run("b", {}, { label: "GIF 处理失败" });
  pool.cancelAll();
  for (const pr of [a, b]) {
    await assert.rejects(() => pr, (e) => e instanceof AppError && e.label === "GIF 处理失败" && e.detail === "已取消");
  }
  assert.ok(FakeWorker.instances[0].terminated, "busy worker terminated");
  assert.equal(pool.pending, 0);
  const c = pool.run("c", {});
  assert.equal(FakeWorker.instances.length, 2, "fresh worker for the next run");
  FakeWorker.instances[1].emit({ id: 3, type: "result", result: "after-cancel" });
  assert.deepEqual(await c, "after-cancel");
});

test("pool ignores messages for unknown or stale task ids", async () => {
  const pool = freshPool();
  const p = pool.run("k", {});
  const w = FakeWorker.instances[0];
  w.emit({ id: 999, type: "result", result: "ghost" });
  w.emit({ id: 1, type: "progress", done: 1, total: 1 });
  w.emit({ data: null });
  w.emit(null);
  w.emit({ id: 1, type: "result", result: "real" });
  assert.deepEqual(await p, "real");
});

test("crash on an already-removed worker is a no-op", async () => {
  const pool = freshPool({ size: 1 });
  const p = pool.run("k", {});
  const w = FakeWorker.instances[0];
  w.emit({ id: 1, type: "result", result: 1 });
  await p;
  w.crash("late");
  assert.equal(pool.pending, 0);
});
