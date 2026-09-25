// web/tests/gif_ops.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  stepIndexKept,
  mergeOrder,
  GIFUCT_ESM_URL,
  decompressFramePatch,
  mapToPalette,
  compositeInto,
  applyDisposal,
  encodeAnimatedGif,
  ensureGifuct,
  loadGifFrames,
  splitGif,
  mergeGif,
} from "../lib/gif_ops.js";

function naiveMap(data, palette) {
  const idx = new Uint8Array((data.length / 4) | 0);
  for (let p = 0, i = 0; i < data.length; i += 4, p++) {
    const r = data[i], g = data[i + 1], b = data[i + 2];
    let best = 0, bestD = Infinity;
    for (let k = 0; k < palette.length; k++) {
      const pr = palette[k][0] - r, pg = palette[k][1] - g, pb = palette[k][2] - b;
      const d = pr * pr + pg * pg + pb * pb;
      if (d < bestD) { bestD = d; best = k; }
    }
    idx[p] = best;
  }
  return idx;
}

function fakeCanvas(w, h, rgba) {
  return {
    width: w,
    height: h,
    getContext() {
      return { getImageData: (x, y, ww, hh) => ({ data: new Uint8ClampedArray(rgba) }) };
    },
  };
}

test("split step keeps first frame at step>=1", () => {
  assert.deepEqual([0, 1, 2, 3].filter((i) => stepIndexKept(i, 2)), [0, 2]);
  assert.deepEqual([0, 1, 2].filter((i) => stepIndexKept(i, 1)), [0, 1, 2]);
});

test("split step clamps step below 1 to keep every frame", () => {
  assert.deepEqual([0, 1, 2].filter((i) => stepIndexKept(i, 0)), [0, 1, 2]);
  assert.deepEqual([0, 1, 2].filter((i) => stepIndexKept(i, -3)), [0, 1, 2]);
  assert.deepEqual([0, 1, 2].filter((i) => stepIndexKept(i, NaN)), [0, 1, 2]);
});

test("merge reverse order", () => {
  assert.deepEqual(mergeOrder(["a", "b"], true), ["b", "a"]);
  assert.deepEqual(mergeOrder(["a", "b"], false), ["a", "b"]);
});

test("gifuct is pinned to the ESM bundle (2.1.2 has no dist/ UMD build)", () => {
  assert.equal(GIFUCT_ESM_URL, "https://cdn.jsdelivr.net/npm/gifuct-js@2.1.2/+esm");
  assert.ok(!/\/dist\//.test(GIFUCT_ESM_URL));
});

test("decompressFramePatch calls gifuct(frame, gct, buildImagePatch) in order", () => {
  const calls = [];
  const gct = { exists: true };
  const frame = { image: { descriptor: { width: 2, height: 2 } } };
  const lib = {
    decompressFrame(...args) {
      calls.push(args);
      return { patch: new Uint8Array(16) };
    },
  };
  const parsed = { gct };
  const patch = decompressFramePatch(lib, parsed, frame);
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], frame);
  assert.equal(calls[0][1], gct);
  assert.equal(calls[0][2], true);
  assert.ok(patch && patch.patch);
});

test("decompressFramePatch returns null for frames gifuct cannot decompress", () => {
  const lib = { decompressFrame: () => undefined };
  assert.equal(decompressFramePatch(lib, { gct: null }, {}), null);
  const noPatch = { decompressFrame: () => ({ dims: {} }) };
  assert.equal(decompressFramePatch(noPatch, { gct: null }, {}), null);
});

test("memoized mapToPalette matches the naive nearest-color result", () => {
  const palette = [];
  for (let i = 0; i < 256; i++) palette.push([i * 7 % 256, i * 13 % 256, i * 29 % 256]);
  const n = 4000;
  const data = new Uint8ClampedArray(n * 4);
  let seed = 12345;
  const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
  for (let i = 0; i < n; i++) {
    const v = Math.floor(rnd() * 40);
    data[i * 4] = v * 6;
    data[i * 4 + 1] = v * 6;
    data[i * 4 + 2] = v * 6;
    data[i * 4 + 3] = 255;
  }
  for (let i = 0; i < 200; i++) {
    const o = Math.floor(rnd() * n) * 4;
    data[o] = Math.floor(rnd() * 256);
    data[o + 1] = Math.floor(rnd() * 256);
    data[o + 2] = Math.floor(rnd() * 256);
  }
  const fast = mapToPalette(data, palette);
  const slow = naiveMap(data, palette);
  assert.deepEqual([...fast], [...slow]);
});

test("compositeInto places a partial patch at its dims offset", () => {
  const buf = new Uint8ClampedArray(4 * 4 * 4);
  const patch = {
    dims: { top: 1, left: 2, width: 2, height: 2 },
    patch: new Uint8ClampedArray([
      255, 0, 0, 255, 0, 255, 0, 255,
      0, 0, 255, 255, 255, 255, 0, 255,
    ]),
  };
  compositeInto(buf, 4, 4, patch);
  const at = (x, y) => [buf[(y * 4 + x) * 4], buf[(y * 4 + x) * 4 + 1], buf[(y * 4 + x) * 4 + 2], buf[(y * 4 + x) * 4 + 3]];
  assert.deepEqual(at(2, 1), [255, 0, 0, 255]);
  assert.deepEqual(at(3, 1), [0, 255, 0, 255]);
  assert.deepEqual(at(2, 2), [0, 0, 255, 255]);
  assert.deepEqual(at(3, 2), [255, 255, 0, 255]);
  assert.deepEqual(at(0, 0), [0, 0, 0, 0]);
});

test("compositeInto skips fully transparent pixels so the previous frame shows through", () => {
  const buf = new Uint8ClampedArray(2 * 2 * 4);
  for (let i = 0; i < 4; i++) {
    buf[i * 4] = 10; buf[i * 4 + 1] = 20; buf[i * 4 + 2] = 30; buf[i * 4 + 3] = 255;
  }
  const patch = {
    dims: { top: 0, left: 0, width: 2, height: 2 },
    patch: new Uint8ClampedArray([0, 0, 0, 0, 9, 9, 9, 255, 0, 0, 0, 0, 0, 0, 0, 0]),
  };
  compositeInto(buf, 2, 2, patch);
  assert.deepEqual([buf[0], buf[1], buf[2], buf[3]], [10, 20, 30, 255]);
  assert.deepEqual([buf[4], buf[5], buf[6], buf[7]], [9, 9, 9, 255]);
});

test("applyDisposal clears the frame rect only for disposal type 2", () => {
  const mk = () => {
    const b = new Uint8ClampedArray(2 * 2 * 4).fill(200);
    return b;
  };
  const dims = { top: 0, left: 0, width: 2, height: 2 };
  const keep = mk();
  applyDisposal(keep, 2, 2, { dims }, 1);
  assert.equal(keep[0], 200);
  const bg = mk();
  applyDisposal(bg, 2, 2, { dims }, 2);
  assert.deepEqual([...bg.slice(0, 4)], [0, 0, 0, 0]);
});

test("encodeAnimatedGif emits a valid GIF89a stream and reports progress", async () => {
  const frames = [
    fakeCanvas(2, 2, [255, 0, 0, 255, 255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255]),
    fakeCanvas(2, 2, [0, 255, 0, 255, 0, 255, 0, 255, 255, 255, 0, 255, 255, 0, 0, 255]),
    fakeCanvas(2, 2, [0, 0, 255, 255, 0, 0, 255, 255, 128, 128, 128, 255, 64, 64, 64, 255]),
  ];
  const seen = [];
  const blob = await encodeAnimatedGif(frames, { durationMs: 100, onProgress: (d, t) => seen.push([d, t]) });
  const bytes = new Uint8Array(await blob.arrayBuffer());
  assert.equal(blob.type, "image/gif");
  assert.equal(String.fromCharCode(...bytes.slice(0, 6)), "GIF89a");
  assert.equal(bytes[bytes.length - 1], 0x3b);
  assert.deepEqual(seen, [[1, 3], [2, 3], [3, 3]]);
});

test("encodeAnimatedGif honours a cancel token requested mid-encode", async () => {
  const frames = [
    fakeCanvas(2, 2, [1, 2, 3, 255, 4, 5, 6, 255, 7, 8, 9, 255, 10, 11, 12, 255]),
    fakeCanvas(2, 2, [12, 11, 10, 255, 9, 8, 7, 255, 6, 5, 4, 255, 3, 2, 1, 255]),
    fakeCanvas(2, 2, [1, 1, 1, 255, 2, 2, 2, 255, 3, 3, 3, 255, 4, 4, 4, 255]),
  ];
  const token = { cancelled: false };
  await assert.rejects(
    () =>
      encodeAnimatedGif(frames, {
        token,
        onProgress: (done) => {
          if (done === 1) token.cancelled = true;
        },
      }),
    (e) => /已取消/.test(String(e && (e.detail || e.message || e)))
  );
});

function installGifEnv(t) {
  const state = { canvases: [], putImageDataCalls: 0, blobNull: false };
  const origDoc = globalThis.document;
  const origCreate = globalThis.createImageBitmap;
  globalThis.document = {
    createElement(tag) {
      assert.equal(tag, "canvas");
      const cv = {
        width: 0,
        height: 0,
        _draws: [],
        _ctx: {
          drawImage(...a) {
            cv._draws.push(a);
          },
          createImageData(w, h) {
            return { data: new Uint8ClampedArray(w * h * 4) };
          },
          putImageData() {
            state.putImageDataCalls += 1;
          },
          getImageData(x, y, w, h) {
            const data = new Uint8ClampedArray(w * h * 4);
            for (let i = 0; i < data.length; i += 4) {
              data[i] = (i / 4) % 256;
              data[i + 1] = (i / 8) % 256;
              data[i + 2] = (i / 16) % 256;
              data[i + 3] = 255;
            }
            return { data };
          },
        },
        getContext() {
          return cv._ctx;
        },
        toBlob(cb, type) {
          if (state.blobNull) cb(null);
          else cb(new Blob([new Uint8Array([1])], { type: type || "image/png" }));
        },
      };
      state.canvases.push(cv);
      return cv;
    },
  };
  globalThis.createImageBitmap = async () => ({
    width: 4,
    height: 4,
    closed: false,
    close() {
      this.closed = true;
    },
  });
  t.after(() => {
    globalThis.document = origDoc;
    if (origCreate === undefined) delete globalThis.createImageBitmap;
    else globalThis.createImageBitmap = origCreate;
  });
  return state;
}

function makeGifuct(opts = {}) {
  const frames = opts.frames || [
    { dims: { top: 0, left: 0, width: 4, height: 4 }, patch: new Uint8ClampedArray(4 * 4 * 4).fill(255) },
    { dims: { top: 0, left: 0, width: 4, height: 4 }, patch: new Uint8ClampedArray(4 * 4 * 4).fill(128) },
  ];
  return {
    parseGIF() {
      if (opts.parseError) throw new Error("corrupt stream");
      return { lsd: { width: 4, height: 4 }, gct: {}, frames };
    },
    decompressFrame(frame) {
      if (frame._null) return undefined;
      if (frame._badPatch) return { dims: {} };
      return { patch: frame.patch, dims: frame.dims, disposalType: 0 };
    },
  };
}

const gifFile = (name = "anim.gif") => ({
  name,
  arrayBuffer: async () => new ArrayBuffer(32),
});

test("ensureGifuct rejects remote import failures as AppError and retries fresh", async () => {
  // Node cannot import https URLs → importFirst rejects without touching the network
  await assert.rejects(() => ensureGifuct(), (e) => {
    assert.equal(e.label, "GIF 处理失败");
    assert.match(e.detail, /无法加载依赖/);
    return true;
  });
  const p1 = ensureGifuct();
  const p2 = ensureGifuct();
  assert.equal(p1, p2, "in-flight promise is memoized");
  await assert.rejects(() => p1, /无法加载依赖/);
});

test("loadGifFrames composites frames onto canvases and skips undecodable ones", async (t) => {
  const state = installGifEnv(t);
  const frames = [
    { dims: { top: 0, left: 0, width: 4, height: 4 }, patch: new Uint8ClampedArray(4 * 4 * 4).fill(255) },
    { _null: true },
    { dims: { top: 0, left: 0, width: 4, height: 4 }, patch: new Uint8ClampedArray(4 * 4 * 4).fill(99) },
  ];
  const out = await loadGifFrames(gifFile(), { gifuct: makeGifuct({ frames }) });
  assert.equal(out.width, 4);
  assert.equal(out.height, 4);
  assert.equal(out.frames.length, 2, "null-patch frame skipped");
  assert.equal(state.putImageDataCalls, 2);
});

test("loadGifFrames validates the gifuct surface and parse failures", async () => {
  await assert.rejects(
    () => loadGifFrames(gifFile(), { gifuct: {} }),
    /gifuct 加载失败/,
  );
  await assert.rejects(
    () => loadGifFrames(gifFile(), { gifuct: makeGifuct({ parseError: true }) }),
    (e) => {
      assert.match(e.detail, /无法读取 GIF: anim\.gif/);
      return true;
    },
  );
});

test("loadGifFrames rejects empty frame lists and honours cancel", async (t) => {
  installGifEnv(t);
  await assert.rejects(
    () => loadGifFrames(gifFile(), { gifuct: makeGifuct({ frames: [{ _badPatch: true }] }) }),
    /GIF 中没有可导出的帧/,
  );
  const token = { cancelled: false };
  const frames = [
    { dims: { top: 0, left: 0, width: 4, height: 4 }, patch: new Uint8ClampedArray(4 * 4 * 4).fill(1) },
    { dims: { top: 0, left: 0, width: 4, height: 4 }, patch: new Uint8ClampedArray(4 * 4 * 4).fill(2) },
  ];
  await assert.rejects(
    () =>
      loadGifFrames(gifFile(), {
        token,
        gifuct: {
          ...makeGifuct({ frames }),
          decompressFrame(frame, gct, flag) {
            token.cancelled = true; // cancel lands before the next frame check
            return makeGifuct({ frames }).decompressFrame(frame, gct, flag);
          },
        },
      }),
    /已取消/,
  );
});

test("splitGif validates the step and exports padded frame files", async (t) => {
  installGifEnv(t);
  await assert.rejects(() => splitGif(gifFile(), { step: 0, gifuct: makeGifuct() }), /抽稀步长至少为 1/);
  const { files } = await splitGif(gifFile("walk.GIF"), {
    step: 2,
    gifuct: makeGifuct({
      frames: [
        { dims: { top: 0, left: 0, width: 4, height: 4 }, patch: new Uint8ClampedArray(64).fill(255) },
        { dims: { top: 0, left: 0, width: 4, height: 4 }, patch: new Uint8ClampedArray(64).fill(128) },
        { dims: { top: 0, left: 0, width: 4, height: 4 }, patch: new Uint8ClampedArray(64).fill(64) },
        { dims: { top: 0, left: 0, width: 4, height: 4 }, patch: new Uint8ClampedArray(64).fill(32) },
      ],
    }),
  });
  assert.deepEqual(
    files.map((f) => f.name),
    ["walk/frame_0001.png", "walk/frame_0002.png"],
    "step 2 keeps frames 0 and 2, renumbered contiguously",
  );
  assert.equal(files[0].blob.type, "image/png");
});

test("splitGif surfaces blob failures and mid-export cancellation", async (t) => {
  const state = installGifEnv(t);
  state.blobNull = true;
  await assert.rejects(
    () => splitGif(gifFile(), { step: 1, gifuct: makeGifuct() }),
    /保存失败/,
  );
  state.blobNull = false;
  // token reads: loadGifFrames frame checks (1,2), splitGif i=0 (3), i=1 (4 → cancelled)
  let reads = 0;
  const token = {
    get cancelled() {
      reads += 1;
      return reads >= 4;
    },
  };
  await assert.rejects(
    () => splitGif(gifFile(), { step: 1, token, gifuct: makeGifuct() }),
    /已取消/,
  );
});

test("mergeGif validates inputs before decoding", async () => {
  await assert.rejects(() => mergeGif([]), /没有可合并的图片/);
  await assert.rejects(
    () => mergeGif([{ name: "a.png" }], { durationMs: 5 }),
    /帧间隔至少 10 毫秒/,
  );
});

test("mergeGif encodes ordered frames into a .gif with progress", async (t) => {
  const state = installGifEnv(t);
  const seen = [];
  const files = [
    { name: "first.png" },
    { name: "second.png" },
  ];
  const out = await mergeGif(files, { durationMs: 40, onProgress: (d, n) => seen.push([d, n]) });
  assert.equal(out.filename, "first.gif");
  assert.equal(out.blob.type, "image/gif");
  const bytes = new Uint8Array(await out.blob.arrayBuffer());
  assert.equal(String.fromCharCode(...bytes.slice(0, 6)), "GIF89a");
  assert.deepEqual(seen, [[1, 2], [2, 2]]);
  assert.equal(state.canvases.length, 2);
  assert.equal(state.canvases[0]._draws.length, 1, "each frame drawn once");
});

test("mergeGif reverse order drives the output name and frame order", async (t) => {
  const state = installGifEnv(t);
  const out = await mergeGif([{ name: "first.png" }, { name: "second.png" }], { reverse: true });
  assert.equal(out.filename, "second.gif");
  assert.equal(state.canvases.length, 2);
});

test("mergeGif cancels between frames", async (t) => {
  installGifEnv(t);
  const token = { cancelled: false };
  let calls = 0;
  const origCreate = globalThis.createImageBitmap;
  globalThis.createImageBitmap = async () => {
    calls += 1;
    if (calls === 1) token.cancelled = true;
    return { width: 4, height: 4, close() {} };
  };
  try {
    await assert.rejects(
      () => mergeGif([{ name: "a.png" }, { name: "b.png" }], { token }),
      /已取消/,
    );
  } finally {
    globalThis.createImageBitmap = origCreate;
  }
});

test("encodeAnimatedGif rejects an empty frame list", async () => {
  await assert.rejects(() => encodeAnimatedGif([]), /没有可合并的图片/);
});

test("lzw handles empty, repetitive, and high-entropy frames", async () => {
  const empty = fakeCanvas(0, 0, []);
  const blob = await encodeAnimatedGif([empty]);
  const bytes = new Uint8Array(await blob.arrayBuffer());
  assert.equal(bytes[bytes.length - 1], 0x3b);

  const alt = [];
  for (let i = 0; i < 16; i++) {
    const rgb = i % 2 === 0 ? [255, 0, 0] : [0, 0, 255];
    alt.push(...rgb, 255);
  }
  await encodeAnimatedGif([fakeCanvas(4, 4, alt)]);

  const w = 256;
  const h = 256;
  const noisy = new Uint8ClampedArray(w * h * 4);
  let seed = 987654321;
  const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
  for (let i = 0; i < w * h; i++) {
    noisy[i * 4] = Math.floor(rnd() * 256);
    noisy[i * 4 + 1] = Math.floor(rnd() * 256);
    noisy[i * 4 + 2] = Math.floor(rnd() * 256);
    noisy[i * 4 + 3] = 255;
  }
  const big = await encodeAnimatedGif([fakeCanvas(w, h, noisy)]);
  const bigBytes = new Uint8Array(await big.arrayBuffer());
  assert.equal(String.fromCharCode(...bigBytes.slice(0, 6)), "GIF89a");
  assert.equal(bigBytes[bigBytes.length - 1], 0x3b);
});


