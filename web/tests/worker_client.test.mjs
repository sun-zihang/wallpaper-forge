import test from "node:test";
import assert from "node:assert/strict";
import { runJob, cancelAllWorkerJobs, hydrate } from "../lib/worker_client.js";
import { AppError } from "../lib/errors.js";

// ---- hydrate (pure) ----

test("hydrate rebuilds wire blob records into Blobs", () => {
  const buf = new ArrayBuffer(4);
  const blob = hydrate({ buf, type: "image/png" });
  assert.ok(blob instanceof Blob);
  assert.equal(blob.type, "image/png");
  const nested = hydrate({ blob: { buf, type: "image/bmp" }, filename: "a.bmp" });
  assert.equal(nested.filename, "a.bmp");
  assert.ok(nested.blob instanceof Blob);
  const listed = hydrate({ files: [{ name: "x", blob: { buf, type: "image/png" } }] });
  assert.equal(listed.files[0].name, "x");
  assert.ok(listed.files[0].blob instanceof Blob);
});

test("hydrate passes through primitives and non-blob objects", () => {
  assert.equal(hydrate("s"), "s");
  assert.equal(hydrate(5), 5);
  assert.equal(hydrate(null), null);
  const obj = { buf: "not-a-buffer", type: "x", other: 1 };
  assert.deepEqual(hydrate(obj), obj);
  assert.deepEqual(hydrate([1, "a"]), [1, "a"]);
});

// ---- upfront cancellation (no canvas needed) ----

test("runJob rejects immediately on a cancelled token with the kind label", async () => {
  await assert.rejects(
    () => runJob("convert_image", { file: {} }, { token: { cancelled: true } }),
    (e) => e instanceof AppError && e.label === "图片处理失败" && e.detail === "已取消",
  );
  await assert.rejects(
    () => runJob("gif_merge", { files: [] }, { token: { cancelled: true } }),
    (e) => e instanceof AppError && e.label === "GIF 处理失败" && e.detail === "已取消",
  );
});

// ---- canvas stubs for the main-thread fallback path ----

function installCanvasStubs(t, { bitmapW = 40, bitmapH = 20 } = {}) {
  const state = { canvases: [], closed: 0, bitmaps: [] };
  const origDoc = globalThis.document;
  const origCreate = globalThis.createImageBitmap;
  globalThis.document = {
    createElement(tag) {
      assert.equal(tag, "canvas");
      const cv = {
        width: 0,
        height: 0,
        getContext(kind) {
          assert.equal(kind, "2d");
          return {
            imageSmoothingQuality: "low",
            globalAlpha: 1,
            font: "",
            fillStyle: "",
            textBaseline: "",
            drawImage() {},
            fillText() {},
            measureText: (s) => ({ width: String(s).length * 10 }),
            createImageData(w, h) {
              return { data: new Uint8ClampedArray(w * h * 4) };
            },
            putImageData() {},
            getImageData(x, y, w, h) {
              const data = new Uint8ClampedArray(w * h * 4);
              for (let i = 0; i < data.length; i++) data[i] = (i * 7 + 3) % 256;
              return { data };
            },
          };
        },
        toBlob(cb, type) {
          cb(new Blob([new Uint8Array([9, 9])], { type: type || "image/png" }));
        },
      };
      state.canvases.push(cv);
      return cv;
    },
  };
  globalThis.createImageBitmap = async (src) => {
    const bmp = { width: bitmapW, height: bitmapH, src, close() { state.closed += 1; } };
    state.bitmaps.push(bmp);
    return bmp;
  };
  t.after(() => {
    globalThis.document = origDoc;
    if (origCreate === undefined) delete globalThis.createImageBitmap;
    else globalThis.createImageBitmap = origCreate;
  });
  return state;
}

function fakeFile(name, bytes = new ArrayBuffer(8)) {
  return { name, arrayBuffer: async () => bytes };
}

test("runJob falls back to inline handlers and returns hydrated Blobs", async (t) => {
  installCanvasStubs(t);
  const out = await runJob("convert_image", { file: fakeFile("a.png"), opts: { format: "BMP" } });
  assert.equal(out.filename, "a.bmp");
  assert.ok(out.blob instanceof Blob);
  assert.equal(out.blob.type, "image/bmp");
});

test("runJob fallback wires watermark jobs through the same payload shape", async (t) => {
  installCanvasStubs(t);
  const out = await runJob("text_watermark", {
    file: fakeFile("b.jpg"),
    opts: { text: "hello", fontSize: 20, position: "center" },
  });
  assert.equal(out.filename, "b_wm.png");
  assert.ok(out.blob instanceof Blob);
});

test("runJob fallback maps non-AppError handler crashes into the kind label", async () => {
  await assert.rejects(
    () => runJob("convert_image", {}),
    (e) => e instanceof AppError && e.label === "图片处理失败" && e.detail.length > 0,
  );
});

test("runJob fallback forwards per-frame progress from gif_merge", async (t) => {
  installCanvasStubs(t);
  const seen = [];
  const out = await runJob(
    "gif_merge",
    { files: [fakeFile("f1.png")], opts: { durationMs: 100 } },
    { onProgress: (done, total) => seen.push([done, total]) },
  );
  assert.match(out.filename, /\.gif$/);
  assert.ok(out.blob instanceof Blob);
  assert.deepEqual(seen, [[1, 1]]);
});

test("cancelAllWorkerJobs is a no-op without a pool", () => {
  assert.doesNotThrow(() => cancelAllWorkerJobs());
});

// ---- pool path (injected FakeWorker; keep last: the pool is a singleton) ----

class FakeWorker {
  static instances = [];
  constructor(url, opts) {
    this.url = url;
    this.opts = opts;
    this.sent = [];
    this.failPost = false;
    FakeWorker.instances.push(this);
  }
  postMessage(data, transfer) {
    if (this.failPost) throw new Error("postMessage failed");
    this.sent.push({ data, transfer: transfer || [] });
  }
  terminate() {}
  emit(data) {
    this.onmessage({ data });
  }
}

const settle = () => new Promise((resolve) => setImmediate(resolve));

test("runJob moves file buffers through the pool with a transfer list", async (t) => {
  const origWorker = globalThis.Worker;
  globalThis.Worker = FakeWorker;
  FakeWorker.instances = [];
  t.after(() => {
    if (origWorker === undefined) delete globalThis.Worker;
    else globalThis.Worker = origWorker;
  });
  const buf = new ArrayBuffer(8);
  const pr = runJob("convert_image", { file: fakeFile("c.png", buf), opts: { format: "BMP" } });
  await settle();
  assert.equal(FakeWorker.instances.length, 1, "module worker spawned");
  const w = FakeWorker.instances[0];
  const msg = w.sent[0].data;
  assert.equal(msg.kind, "convert_image");
  assert.deepEqual(w.sent[0].transfer, [buf]);
  w.emit({
    id: msg.id,
    type: "result",
    result: { blob: { buf: new ArrayBuffer(4), type: "image/bmp" }, filename: "c.bmp" },
  });
  const out = await pr;
  assert.equal(out.filename, "c.bmp");
  assert.ok(out.blob instanceof Blob);
});

// The pool singleton built by the first pool test persists for the rest of the
// file; each test re-arms globalThis.Worker so ensurePool() keeps using it.
function armPool(t) {
  const orig = globalThis.Worker;
  globalThis.Worker = FakeWorker;
  t.after(() => {
    if (orig === undefined) delete globalThis.Worker;
    else globalThis.Worker = orig;
  });
}

test("runJob pool path maps worker errors back to AppError", async (t) => {
  armPool(t);
  const pr = runJob("gif_split", { file: fakeFile("d.gif"), opts: { step: 1 } });
  await settle();
  const w = FakeWorker.instances[FakeWorker.instances.length - 1];
  const msg = w.sent[w.sent.length - 1].data;
  w.emit({ id: msg.id, type: "error", label: "GIF 处理失败", detail: "bad gif" });
  await assert.rejects(
    () => pr,
    (e) => e instanceof AppError && e.label === "GIF 处理失败" && e.detail === "bad gif",
  );
});

test("runJob pool path wraps low-level dispatch failures with the kind label", async (t) => {
  armPool(t);
  // the worker reused from the previous test is idle here
  const w = FakeWorker.instances[FakeWorker.instances.length - 1];
  w.failPost = true;
  try {
    const p2 = runJob("convert_image", { file: fakeFile("e2.png"), opts: {} });
    // the dispatch fails inside the next microtask, before assert.rejects can
    // attach — silence the transient unhandled-rejection window
    p2.catch(() => {});
    await settle();
    await assert.rejects(
      () => p2,
      (e) => e instanceof AppError && e.label === "图片处理失败" && /postMessage failed/.test(e.detail),
    );
  } finally {
    w.failPost = false;
  }
});

test("cancelAllWorkerJobs cancels the in-flight pool job", async (t) => {
  armPool(t);
  const pr = runJob("gif_merge", { files: [fakeFile("f.png")], opts: { durationMs: 100 } });
  await settle();
  cancelAllWorkerJobs();
  await assert.rejects(
    () => pr,
    (e) => e instanceof AppError && e.label === "GIF 处理失败" && e.detail === "已取消",
  );
});

// ---- unpack jobs through runJob (P1) ----

function buildPkgBytes(files, magic = "PKGV0005") {
  const enc = new TextEncoder();
  const names = Object.keys(files);
  const header = enc.encode(magic);
  const blobs = names.map((n) => files[n]);
  const parts = [];
  const pushU32 = (v) => {
    parts.push(new Uint8Array(new DataView(new ArrayBuffer(4)).buffer));
    const last = parts.at(-1);
    new DataView(last.buffer).setUint32(0, v, true);
  };
  pushU32(header.length);
  parts.push(header);
  pushU32(names.length);
  let off = 0;
  names.forEach((n, i) => {
    const nb = enc.encode(n);
    pushU32(nb.length);
    parts.push(nb);
    pushU32(off);
    pushU32(blobs[i].length);
    off += blobs[i].length;
  });
  parts.push(...blobs);
  const total = parts.reduce((s, p) => s + p.length, 0);
  const out = new Uint8Array(total);
  let p = 0;
  for (const part of parts) {
    out.set(part, p);
    p += part.length;
  }
  return out;
}

test("runJob fallback unpacks a pkg and hydrates entries into Blobs", async () => {
  const pkg = buildPkgBytes({
    "img/a.png": new Uint8Array([9, 8, 7]),
    "readme.txt": new TextEncoder().encode("hi"),
  });
  const file = new File([pkg], "wallpaper.pkg");
  const r = await runJob("unpack_pkg", { file });
  assert.deepEqual(
    r.files.map((f) => f.name).sort(),
    ["img/a.png", "readme.txt"],
  );
  for (const f of r.files) {
    assert.ok(f.blob instanceof Blob, "hydrate 把 wire 记录还原成 Blob");
  }
});

test("runJob fallback unpack_mpkg garbage maps to the MPKG label", async () => {
  const file = new File([new Uint8Array(8)], "bad.mpkg");
  await assert.rejects(
    () => runJob("unpack_mpkg", { file }),
    (e) => e instanceof AppError && e.label === "MPKG 解包失败",
  );
});
