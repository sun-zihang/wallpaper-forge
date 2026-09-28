// Page-facing job client. Files are read to ArrayBuffers on the main thread
// (unavoidable I/O) and then MOVED into the worker via a transfer list instead
// of being cloned by postMessage; results come back the same way and are
// re-hydrated into Blobs. If module Workers are unavailable the same handlers
// run inline on the main thread, preserving the pre-worker behavior.
import { AppError } from "./errors.js";
import { WorkerPool } from "./worker_pool.js";
import { handlers } from "./process_worker.js";

const KIND_LABELS = {
  convert_image: "图片处理失败",
  text_watermark: "图片处理失败",
  image_watermark: "图片处理失败",
  gif_split: "GIF 处理失败",
  gif_merge: "GIF 处理失败",
  unpack_pkg: "PKG 解包失败",
  unpack_tex: "TEX 解析失败",
  unpack_mpkg: "MPKG 解包失败",
};

let pool = null;
let poolUnavailable = false;

function ensurePool() {
  if (poolUnavailable || typeof Worker !== "function") return null;
  if (!pool) {
    try {
      pool = new WorkerPool({ workerUrl: new URL("./process_worker.js", import.meta.url), size: 2 });
    } catch {
      poolUnavailable = true;
      return null;
    }
  }
  return pool;
}

// Replaces wire blob records ({ buf, type } — exactly those two keys) with
// real Blobs, recursively. Anything else passes through untouched.
export function hydrate(value) {
  if (!value || typeof value !== "object") return value;
  const keys = Object.keys(value);
  if (
    keys.length === 2 &&
    "buf" in value &&
    "type" in value &&
    (value.buf instanceof ArrayBuffer || ArrayBuffer.isView(value.buf))
  ) {
    return new Blob([value.buf], { type: value.type || "application/octet-stream" });
  }
  if (Array.isArray(value)) return value.map(hydrate);
  const out = {};
  for (const k of keys) out[k] = hydrate(value[k]);
  return out;
}

async function wireFile(f) {
  const buf = await f.arrayBuffer();
  return { buf, name: f.name || "" };
}

function mapJobError(label, e) {
  if (e instanceof AppError) return e;
  return new AppError(label, e && e.message ? e.message : String(e));
}

export async function runJob(kind, { file, mark, files = [], opts = {} } = {}, { onProgress, token } = {}) {
  const label = KIND_LABELS[kind] || "处理失败";
  if (token && token.cancelled) throw new AppError(label, "已取消");
  const wire = { opts };
  const transfer = [];
  if (file) {
    wire.file = await wireFile(file);
    transfer.push(wire.file.buf);
  }
  if (mark) {
    wire.mark = await wireFile(mark);
    transfer.push(wire.mark.buf);
  }
  if (files.length) {
    wire.files = [];
    for (const f of files) {
      const w = await wireFile(f);
      wire.files.push(w);
      transfer.push(w.buf);
    }
  }
  const p = ensurePool();
  if (!p) {
    try {
      const out = await handlers[kind](wire, onProgress ? (m) => onProgress(m.done, m.total) : undefined);
      return hydrate(out.result);
    } catch (e) {
      throw mapJobError(label, e);
    }
  }
  try {
    const result = await p.run(kind, wire, { transfer, onProgress, label });
    return hydrate(result);
  } catch (e) {
    throw mapJobError(label, e);
  }
}

export function cancelAllWorkerJobs() {
  if (pool) pool.cancelAll();
}
