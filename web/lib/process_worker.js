// Worker entry: thin router from wire messages to the shared ops modules.
// The handlers are exported so the main-thread fallback (worker_client.js) and
// the node tests run the exact same code the worker runs.
import { convertImage } from "./image_ops.js";
import { splitGif, mergeGif } from "./gif_ops.js";
import { addTextWatermark, addImageWatermark } from "./annotate.js";
import { extractPkg } from "./we_pkg.js";
import { extractTex } from "./we_tex.js";
import { extractMpkg } from "./we_mpkg.js";

function toFile({ buf, name }) {
  return new File([buf], name || "input");
}

// Blobs cannot cross the transferable boundary by address, so each output is
// materialized as an ArrayBuffer once inside the worker and moved to the main
// thread with a transfer list (zero-copy handoff).
async function toWireBlob(blob) {
  const buf = await blob.arrayBuffer();
  return { data: { buf, type: blob.type }, transfers: [buf] };
}

// Unpack results are { files: [{ name, blob }] } — move every extracted file
// across the wire the same way. Unpack libs hand out Uint8Array slices (no
// .arrayBuffer()), Blobs from other ops already have one.
async function toWireFiles(files) {
  const out = [];
  const transfers = [];
  for (const f of files) {
    const b = f.blob;
    const buf = typeof b.arrayBuffer === "function" ? await b.arrayBuffer() : b.slice().buffer;
    out.push({ name: f.name, blob: { buf, type: b.type } });
    transfers.push(buf);
  }
  return { files: out, transfers };
}

export const handlers = {
  async convert_image(p) {
    const r = await convertImage(toFile(p.file), p.opts || {});
    const { data, transfers } = await toWireBlob(r.blob);
    return { result: { blob: data, filename: r.filename }, transfers };
  },
  async text_watermark(p) {
    const r = await addTextWatermark(toFile(p.file), p.opts || {});
    const { data, transfers } = await toWireBlob(r.blob);
    return { result: { blob: data, filename: r.filename }, transfers };
  },
  async image_watermark(p) {
    const r = await addImageWatermark(toFile(p.file), toFile(p.mark), p.opts || {});
    const { data, transfers } = await toWireBlob(r.blob);
    return { result: { blob: data, filename: r.filename }, transfers };
  },
  async gif_split(p) {
    const r = await splitGif(toFile(p.file), p.opts || {});
    const files = [];
    const transfers = [];
    for (const f of r.files) {
      const buf = await f.blob.arrayBuffer();
      // nested under `blob` so hydrate() rebuilds { name, blob } items
      files.push({ name: f.name, blob: { buf, type: f.blob.type } });
      transfers.push(buf);
    }
    return { result: { files }, transfers };
  },
  async gif_merge(p, send) {
    const opts = { ...(p.opts || {}) };
    if (send) {
      opts.onProgress = (done, total) => send({ type: "progress", done, total });
    }
    const r = await mergeGif(p.files.map(toFile), opts);
    const { data, transfers } = await toWireBlob(r.blob);
    return { result: { blob: data, filename: r.filename }, transfers };
  },
  async unpack_pkg(p) {
    const r = extractPkg(new Uint8Array(p.file.buf));
    const { files, transfers } = await toWireFiles(r.files);
    return { result: { files }, transfers };
  },
  async unpack_tex(p) {
    const base = (p.file.name || "texture").replace(/\.[^.]+$/, "");
    const r = extractTex(new Uint8Array(p.file.buf), base);
    const { files, transfers } = await toWireFiles(r.files ? r.files : [r]);
    return { result: { files }, transfers };
  },
  async unpack_mpkg(p) {
    const r = extractMpkg(new Uint8Array(p.file.buf));
    const { files, transfers } = await toWireFiles(r.files);
    return { result: { files }, transfers };
  },
};

export function installHandlers(target) {
  target.onmessage = async (ev) => {
    const msg = ev && ev.data;
    if (!msg || typeof msg.id !== "number" || !handlers[msg.kind]) return;
    const send = (m) => target.postMessage({ id: msg.id, ...m });
    try {
      const { result, transfers = [] } = await handlers[msg.kind](msg.payload || {}, send);
      target.postMessage({ id: msg.id, type: "result", result }, transfers.slice());
    } catch (e) {
      const label = e && e.label ? e.label : "处理失败";
      const detail = e && e.detail ? e.detail : e && e.message ? e.message : String(e);
      target.postMessage({ id: msg.id, type: "error", label, detail });
    }
  };
}

// Module workers see WorkerGlobalScope; the main thread and node tests do not.
if (typeof WorkerGlobalScope !== "undefined") {
  installHandlers(self);
}
