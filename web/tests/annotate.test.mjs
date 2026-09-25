import test from "node:test";
import assert from "node:assert/strict";
import {
  addImageWatermark,
  addTextWatermark,
  cropBoxValid,
  cropCanvas,
  pastePos,
  POSITIONS,
} from "../lib/annotate.js";

test("crop validation matches desktop bounds rule", () => {
  assert.equal(cropBoxValid([0, 0, 32, 24], 64, 48), true);
  assert.equal(cropBoxValid([0, 0, 999, 999], 64, 48), false);
  assert.equal(cropBoxValid([10, 10, 10, 20], 64, 48), false);
});

test("crop rejects negative and non-finite edges", () => {
  assert.equal(cropBoxValid([-1, 0, 10, 10], 64, 48), false);
  assert.equal(cropBoxValid([0, 0, NaN, 10], 64, 48), false);
  assert.equal(cropBoxValid([0, 0, Infinity, 10], 64, 48), false);
});

test("paste rejects unknown position", () => {
  assert.throws(
    () => pastePos(100, 80, 10, 10, "middle"),
    /未知水印位置: middle/,
  );
});

test("paste position top_left and top_right", () => {
  assert.deepEqual(pastePos(100, 80, 10, 10, "top_left", 4), [4, 4]);
  assert.deepEqual(pastePos(100, 80, 10, 10, "top_right", 4), [86, 4]);
  assert.deepEqual(pastePos(100, 80, 10, 10, "bottom_left", 4), [4, 66]);
});

test("paste position bottom_right", () => {
  const [x, y] = pastePos(100, 80, 10, 10, "bottom_right", 4);
  assert.equal(x, 100 - 10 - 4);
  assert.equal(y, 80 - 10 - 4);
});

test("paste position center", () => {
  assert.deepEqual(pastePos(100, 80, 10, 10, "center", 4), [45, 35]);
});

test("positions set same as desktop", () => {
  assert.deepEqual([...POSITIONS].sort(), [
    "bottom_left", "bottom_right", "center", "top_left", "top_right",
  ]);
});

test("addTextWatermark rejects empty text before touching the canvas", async () => {
  await assert.rejects(
    () => addTextWatermark({}, { text: "" }),
    /水印文字不能为空/,
  );
  await assert.rejects(() => addTextWatermark({}, {}), /水印文字不能为空/);
});

test("addImageWatermark rejects out-of-range scale and opacity before decoding", async () => {
  await assert.rejects(
    () => addImageWatermark({}, {}, { scale: 0.01 }),
    /水印缩放比例/,
  );
  await assert.rejects(
    () => addImageWatermark({}, {}, { scale: 1.5 }),
    /水印缩放比例/,
  );
  await assert.rejects(
    () => addImageWatermark({}, {}, { opacity: -0.1 }),
    /透明度/,
  );
  await assert.rejects(
    () => addImageWatermark({}, {}, { opacity: 1.1 }),
    /透明度/,
  );
});

function installDrawEnv(t, { bitmapW = 200, bitmapH = 100 } = {}) {
  const state = { canvases: [], bitmaps: [] };
  const origDoc = globalThis.document;
  const origCreate = globalThis.createImageBitmap;
  globalThis.document = {
    createElement(tag) {
      assert.equal(tag, "canvas");
      const calls = [];
      const ctx = {
        imageSmoothingQuality: "low",
        globalAlpha: 1,
        font: "",
        fillStyle: "",
        textBaseline: "",
        drawImage(...a) {
          calls.push(a);
        },
        fillText(...a) {
          calls.push(["fillText", ...a]);
        },
        measureText(text) {
          return { width: String(text).length * 8 };
        },
        getImageData() {
          return { data: new Uint8ClampedArray(4), width: 1, height: 1 };
        },
        _calls: calls,
      };
      const cv = {
        width: 0,
        height: 0,
        _ctx: ctx,
        _toBlob: null,
        getContext() {
          return ctx;
        },
        toBlob(cb, type) {
          cv._toBlob = type;
          cb(new Blob([new Uint8Array([1])], { type: type || "image/png" }));
        },
      };
      state.canvases.push(cv);
      return cv;
    },
  };
  globalThis.createImageBitmap = async (file) => {
    const bmp = {
      name: file && file.name,
      width: bitmapW,
      height: bitmapH,
      closed: false,
      close() {
        bmp.closed = true;
      },
    };
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

test("cropCanvas draws the valid region and rejects out-of-bounds boxes", (t) => {
  const state = installDrawEnv(t);
  const src = { width: 100, height: 80 };
  const out = cropCanvas(src, [10, 20, 60, 70]);
  assert.equal(out.width, 50);
  assert.equal(out.height, 50);
  assert.deepEqual(state.canvases[0]._ctx._calls[0], [src, 10, 20, 50, 50, 0, 0, 50, 50]);
  assert.throws(() => cropCanvas(src, [10, 20, 500, 70]), /裁剪区域无效/);
  assert.throws(() => cropCanvas(src, [NaN, 0, 10, 10]), /裁剪区域无效/);
});

test("addTextWatermark draws at the requested position and names _wm.png", async (t) => {
  const state = installDrawEnv(t);
  const out = await addTextWatermark(
    { name: "photo.png" },
    { text: "hello", position: "center", margin: 8 },
  );
  assert.equal(out.filename, "photo_wm.png");
  assert.equal(out.blob.type, "image/png");
  const canvas = state.canvases[0];
  assert.equal(canvas.width, 200);
  assert.equal(canvas.height, 100);
  const ctx = canvas._ctx;
  assert.equal(ctx.font, "32px sans-serif");
  assert.equal(ctx.textBaseline, "top");
  const tw = 5 * 8;
  const th = 32 * 1.2;
  const fill = ctx._calls.find((c) => Array.isArray(c) && c[0] === "fillText");
  assert.equal(fill[1], "hello");
  assert.equal(fill[2], (200 - tw) >> 1);
  assert.equal(fill[3], (100 - th) >> 1);
  assert.equal(state.bitmaps[0].closed, true, "bitmap released");
  // base image was drawn full-size first
  const draw = ctx._calls.find((c) => Array.isArray(c) && c[0] !== "fillText");
  assert.deepEqual(draw.slice(1), [0, 0]);
});

test("addTextWatermark rejects when canvas.toBlob fails", async (t) => {
  const state = installDrawEnv(t);
  const origDoc = globalThis.document;
  const failing = {
    createElement(tag) {
      const cv = origDoc.createElement(tag);
      cv.toBlob = (cb) => cb(null);
      return cv;
    },
  };
  globalThis.document = failing;
  try {
    await assert.rejects(
      () => addTextWatermark({ name: "a.png" }, { text: "x" }),
      /保存失败/,
    );
  } finally {
    globalThis.document = origDoc;
  }
});

test("addImageWatermark composites scaled mark with opacity", async (t) => {
  const state = installDrawEnv(t);
  const out = await addImageWatermark(
    { name: "base.jpeg" },
    { name: "mark.png" },
    { scale: 0.5, position: "bottom_right", margin: 4, opacity: 0.6 },
  );
  assert.equal(out.filename, "base_wm.png");
  assert.equal(out.blob.type, "image/png");
  assert.equal(state.canvases.length, 2, "main + offscreen");
  const off = state.canvases[1];
  assert.equal(off.width, 100, "200 * 0.5");
  assert.equal(off._ctx.globalAlpha, 0.6);
  const main = state.canvases[0]._ctx;
  const draws = main._calls.filter((c) => Array.isArray(c) && c[0] !== "fillText");
  assert.equal(draws.length, 2, "base + mark");
  assert.deepEqual(draws[0].slice(1), [0, 0]);
  const x = 200 - 100 - 4;
  const y = 100 - Math.max(1, Math.round(100 * (100 / 200))) - 4;
  assert.deepEqual(draws[1].slice(1), [x, y]);
  assert.equal(state.bitmaps[0].closed, true);
  assert.equal(state.bitmaps[1].closed, true);
});

test("addImageWatermark propagates decode failure", async (t) => {
  installDrawEnv(t);
  const origCreate = globalThis.createImageBitmap;
  let calls = 0;
  globalThis.createImageBitmap = async () => {
    calls += 1;
    if (calls === 2) throw new Error("bad mark");
    return { width: 10, height: 10, close() {} };
  };
  try {
    await assert.rejects(
      () => addImageWatermark({ name: "a.png" }, { name: "b.png" }),
      /无法读取图片/,
    );
  } finally {
    globalThis.createImageBitmap = origCreate;
  }
});
