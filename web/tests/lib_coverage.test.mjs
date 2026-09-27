// web/tests/lib_coverage.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { createCanvas, encodeCanvas } from "../lib/canvas_env.js";
import { classifyError, friendlyError } from "../lib/errors.js";

test("createCanvas uses document when available", () => {
  const origDoc = globalThis.document;
  globalThis.document = { createElement: () => ({ width: 0, height: 0 }) };
  try {
    const c = createCanvas(10, 20);
    assert.equal(c.width, 10);
    assert.equal(c.height, 20);
  } finally {
    globalThis.document = origDoc;
  }
});

test("createCanvas falls back to OffscreenCanvas", () => {
  const origDoc = globalThis.document;
  delete globalThis.document;
  globalThis.OffscreenCanvas = class {
    constructor(w, h) {
      this.width = w;
      this.height = h;
    }
  };
  try {
    const c = createCanvas(5, 6);
    assert.equal(c.width, 5);
  } finally {
    globalThis.OffscreenCanvas = undefined;
    globalThis.document = origDoc;
  }
});

test("createCanvas throws without any canvas impl", () => {
  const origDoc = globalThis.document;
  const origOff = globalThis.OffscreenCanvas;
  delete globalThis.document;
  globalThis.OffscreenCanvas = undefined;
  try {
    assert.throws(() => createCanvas(1, 1), /no canvas/);
  } finally {
    globalThis.OffscreenCanvas = origOff;
    globalThis.document = origDoc;
  }
});

test("encodeCanvas uses toBlob when available", async () => {
  const blob = new Blob(["x"]);
  const canvas = { toBlob: (cb) => cb(blob) };
  assert.equal(await encodeCanvas(canvas, "image/png", undefined, "t"), blob);
});

test("encodeCanvas falls back to convertToBlob", async () => {
  const blob = new Blob(["y"]);
  const canvas = { convertToBlob: async () => blob };
  assert.equal(await encodeCanvas(canvas, "image/png", undefined, "t"), blob);
});

test("encodeCanvas wraps convertToBlob failures", async () => {
  const canvas = {
    convertToBlob: async () => {
      throw new Error("boom");
    },
  };
  await assert.rejects(() => encodeCanvas(canvas, "image/png", undefined, "t"), /保存失败/);
});

test("classifyError categorizes corrupt files", () => {
  const c = classifyError(new Error("文件头无法识别为图片"));
  assert.equal(c.category, "corrupt");
});

test("classifyError categorizes engine failures", () => {
  const c = classifyError(new Error("视频引擎加载失败"));
  assert.equal(c.category, "engine");
  assert.match(c.advice, /Chrome/);
});

test("classifyError categorizes limits", () => {
  const c = classifyError(new Error("单文件超过 100MB 上限"));
  assert.equal(c.category, "limit");
});

test("classifyError falls back to unknown", () => {
  const c = classifyError(new Error("something odd"));
  assert.equal(c.category, "unknown");
});

test("friendlyError returns advice for known categories", () => {
  assert.match(friendlyError(new Error("文件头无法识别")), /文件损坏/);
});
