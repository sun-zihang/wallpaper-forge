import test from "node:test";
import assert from "node:assert/strict";
import { handlers, installHandlers } from "../lib/process_worker.js";

function installCanvasStubs(t, { bitmapW = 8, bitmapH = 6 } = {}) {
  const state = { canvases: [], closed: 0 };
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
            imageSmoothingQuality: "high",
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
              for (let i = 0; i < data.length; i++) data[i] = (i * 11 + 5) % 256;
              return { data };
            },
          };
        },
        toBlob(cb, type) {
          cb(new Blob([new Uint8Array([1, 2, 3])], { type: type || "image/png" }));
        },
      };
      state.canvases.push(cv);
      return cv;
    },
  };
  globalThis.createImageBitmap = async () => ({
    width: bitmapW,
    height: bitmapH,
    close() {
      state.closed += 1;
    },
  });
  t.after(() => {
    globalThis.document = origDoc;
    if (origCreate === undefined) delete globalThis.createImageBitmap;
    else globalThis.createImageBitmap = origCreate;
  });
  return state;
}

function fakeFile(name, bytes = new ArrayBuffer(8)) {
  return { buf: bytes, name };
}

const FAKE_GIFUCT = {
  parseGIF: () => ({ lsd: { width: 2, height: 2 }, frames: [{}] }),
  decompressFrame: () => ({
    patch: new Uint8Array([255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 255, 255, 255, 255]),
    dims: { top: 0, left: 0, width: 2, height: 2 },
    disposalType: 0,
  }),
};

test("convert_image handler returns wire blob + filename", async (t) => {
  installCanvasStubs(t);
  const { result, transfers } = await handlers.convert_image({
    file: fakeFile("shot.final.png"),
    opts: { format: "BMP" },
  });
  assert.equal(result.filename, "shot.final.bmp");
  assert.equal(result.blob.type, "image/bmp");
  assert.ok(result.blob.buf instanceof ArrayBuffer);
  assert.equal(transfers.length, 1);
  assert.equal(transfers[0], result.blob.buf);
});

test("text_watermark handler passes opts through", async (t) => {
  installCanvasStubs(t);
  const { result } = await handlers.text_watermark({
    file: fakeFile("b.jpg"),
    opts: { text: "hi", fontSize: 20, position: "center" },
  });
  assert.equal(result.filename, "b_wm.png");
});

test("image_watermark handler composes base and mark", async (t) => {
  installCanvasStubs(t);
  const { result, transfers } = await handlers.image_watermark({
    file: fakeFile("base.png"),
    mark: fakeFile("mark.png"),
    opts: { scale: 0.5, opacity: 1, position: "top_left" },
  });
  assert.equal(result.filename, "base_wm.png");
  assert.equal(transfers.length, 1);
});

test("gif_split handler nests each frame as a wire blob", async (t) => {
  installCanvasStubs(t);
  const { result, transfers } = await handlers.gif_split({
    file: fakeFile("anim.gif"),
    opts: { step: 1, gifuct: FAKE_GIFUCT },
  });
  assert.equal(result.files.length, 1);
  assert.equal(result.files[0].name, "anim/frame_0001.png");
  assert.equal(result.files[0].blob.type, "image/png");
  assert.deepEqual(transfers, [result.files[0].blob.buf]);
});

test("gif_split handler surfaces AppError details from bad input", async () => {
  await assert.rejects(
    () => handlers.gif_split({ file: fakeFile("a.gif"), opts: { step: 0, gifuct: FAKE_GIFUCT } }),
    (e) => e.label === "GIF 处理失败" && /抽稀步长/.test(e.detail),
  );
});

test("gif_merge handler forwards frame progress through send", async (t) => {
  installCanvasStubs(t);
  const sent = [];
  const { result } = await handlers.gif_merge(
    { files: [fakeFile("f1.png")], opts: { durationMs: 100, loop: 0, reverse: false } },
    (m) => sent.push(m),
  );
  assert.match(result.filename, /^f1\.gif$/);
  assert.deepEqual(sent, [{ type: "progress", done: 1, total: 1 }]);
});

test("gif_merge handler omits progress when send is unavailable", async (t) => {
  installCanvasStubs(t);
  const { result } = await handlers.gif_merge({
    files: [fakeFile("f2.png")],
    opts: { durationMs: 100 },
  });
  assert.match(result.filename, /^f2\.gif$/);
});

test("installHandlers routes results and transfers on the target", async (t) => {
  installCanvasStubs(t);
  const target = { posted: [] };
  target.postMessage = (data, transfers) => target.posted.push({ data, transfers });
  installHandlers(target);
  assert.equal(typeof target.onmessage, "function");
  target.onmessage({
    data: { id: 1, kind: "convert_image", payload: { file: fakeFile("x.png"), opts: { format: "PNG" } } },
  });
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(target.posted.length, 1);
  assert.equal(target.posted[0].data.id, 1);
  assert.equal(target.posted[0].data.type, "result");
  assert.ok(Array.isArray(target.posted[0].transfers));
});

test("installHandlers posts structured errors for failing jobs", async () => {
  const target = { posted: [] };
  target.postMessage = (data) => target.posted.push(data);
  installHandlers(target);
  target.onmessage({ data: { id: 2, kind: "convert_image", payload: { file: { buf: null, name: "x" }, opts: { format: "nope" } } } });
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(target.posted.length, 1);
  assert.equal(target.posted[0].type, "error");
  assert.equal(target.posted[0].label, "图片处理失败");
  assert.match(target.posted[0].detail, /不支持的输出格式/);
});

test("installHandlers ignores malformed and unknown messages", async () => {
  const target = { posted: [] };
  target.postMessage = (data) => target.posted.push(data);
  installHandlers(target);
  target.onmessage(null);
  target.onmessage({ data: null });
  target.onmessage({ data: { kind: "convert_image" } });
  target.onmessage({ data: { id: 3 } });
  target.onmessage({ data: { id: 3, kind: "no_such_kind", payload: {} } });
  assert.equal(target.posted.length, 0);
});
