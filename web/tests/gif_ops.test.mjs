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


