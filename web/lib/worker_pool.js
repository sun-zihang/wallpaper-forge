// Minimal worker pool over native module Workers. Jobs are dispatched with a
// transfer list so file buffers move by address instead of being cloned; a
// cancel terminates the busy worker (dropping its wasm heap) and a replacement
// spawns lazily on the next run().
import { AppError } from "./errors.js";

export class WorkerPool {
  constructor({ workerUrl, size = 2, WorkerCtor = globalThis.Worker, workerOptions = { type: "module" } }) {
    if (typeof WorkerCtor !== "function") {
      throw new Error("Worker constructor unavailable");
    }
    this._url = workerUrl;
    this._opts = workerOptions;
    this._Ctor = WorkerCtor;
    this._size = Math.max(1, size | 0);
    this._workers = new Set();
    this._idle = [];
    this._queue = [];
    this._tasks = new Map();
    this._seq = 0;
  }

  _spawn() {
    const w = new this._Ctor(this._url, this._opts);
    w.onmessage = (ev) => this._onMessage(w, ev && ev.data);
    w.onerror = (ev) => this._failWorker(w, (ev && ev.message) || "worker error");
    this._workers.add(w);
    return w;
  }

  _acquire() {
    if (this._idle.length) return this._idle.pop();
    if (this._workers.size < this._size) return this._spawn();
    return null;
  }

  run(kind, payload, { transfer = [], onProgress, label = "处理失败" } = {}) {
    return new Promise((resolve, reject) => {
      const id = ++this._seq;
      this._tasks.set(id, { resolve, reject, onProgress, label });
      const w = this._acquire();
      if (w) this._dispatch(w, id, kind, payload, transfer);
      else this._queue.push({ id, kind, payload, transfer });
    });
  }

  _dispatch(w, id, kind, payload, transfer) {
    const task = this._tasks.get(id);
    if (!task) return;
    task.worker = w;
    try {
      w.postMessage({ id, kind, payload }, transfer.slice());
    } catch (e) {
      this._tasks.delete(id);
      task.reject(e);
      this._idle.push(w);
      this._pump();
    }
  }

  _onMessage(w, msg) {
    if (!msg || typeof msg.id !== "number") return;
    const task = this._tasks.get(msg.id);
    if (!task) return;
    if (msg.type === "progress") {
      if (task.onProgress) task.onProgress(msg.done, msg.total);
      return;
    }
    this._tasks.delete(msg.id);
    this._idle.push(w);
    if (msg.type === "error") {
      task.reject(new AppError(msg.label || "处理失败", msg.detail || ""));
    } else {
      task.resolve(msg.result);
    }
    this._pump();
  }

  _failWorker(w, message) {
    if (!this._workers.has(w)) return;
    this._workers.delete(w);
    this._idle = this._idle.filter((x) => x !== w);
    for (const [id, task] of [...this._tasks]) {
      if (task.worker !== w) continue;
      this._tasks.delete(id);
      task.reject(new AppError(task.label, `处理线程崩溃: ${message}`));
    }
    this._pump();
  }

  _pump() {
    while (this._queue.length) {
      const w = this._acquire();
      if (!w) return;
      const t = this._queue.shift();
      this._dispatch(w, t.id, t.kind, t.payload, t.transfer);
    }
  }

  // Rejects queued and in-flight tasks, then tears down every worker so a
  // cancelled job cannot keep burning CPU inside its wasm heap.
  cancelAll() {
    const tasks = [...this._tasks.values()];
    this._tasks.clear();
    this._queue.length = 0;
    for (const w of this._workers) {
      try {
        w.terminate();
      } catch { /* already gone */ }
    }
    this._workers.clear();
    this._idle.length = 0;
    for (const task of tasks) {
      task.reject(new AppError(task.label, "已取消"));
    }
  }

  get pending() {
    return this._tasks.size;
  }
}
