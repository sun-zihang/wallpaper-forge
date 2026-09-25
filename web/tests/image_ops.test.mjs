import test from "node:test";
import assert from "node:assert/strict";
import { OUT_EXTS, IMAGE_EXTS, OUT_FORMATS, outputExtFor, qualityExts, canvasToBmp, convertImage, loadImageBitmap } from "../lib/image_ops.js";

function fakeCanvas(w, h, rgba) {
  return {
    width: w,
    height: h,
    getContext() {
      return { getImageData: () => ({ data: new Uint8ClampedArray(rgba) }) };
    },
  };
}

test("output ext mapping", () => {
  assert.equal(outputExtFor("PNG"), ".png");
  assert.equal(outputExtFor("JPG"), ".jpg");
  assert.equal(outputExtFor("JPEG"), ".jpg");
  assert.equal(outputExtFor("jpeg"), ".jpg");
  assert.equal(outputExtFor("WebP"), ".webp");
  assert.equal(outputExtFor("BMP"), ".bmp");
  assert.equal(outputExtFor("GIF"), ".gif");
  assert.ok(OUT_EXTS.includes(".webp"));
  assert.ok(OUT_EXTS.includes(".bmp"));
});

test("output ext rejects unknown format", () => {
  assert.throws(() => outputExtFor("tiff"), /不支持的输出格式/);
  assert.throws(() => outputExtFor(""), /不支持的输出格式/);
});

test("quality only for lossy", () => {
  assert.ok(qualityExts().has(".jpg"));
  assert.ok(qualityExts().has(".webp"));
  assert.ok(!qualityExts().has(".png"));
});

test("format tables stay aligned with each other", () => {
  assert.deepEqual(OUT_FORMATS, ["PNG", "JPG", "WebP", "BMP", "GIF"]);
  assert.deepEqual(OUT_EXTS, [".png", ".jpg", ".webp", ".bmp", ".gif"]);
  assert.deepEqual(IMAGE_EXTS, [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"]);
  for (const fmt of OUT_FORMATS) {
    assert.ok(OUT_EXTS.includes(outputExtFor(fmt)), `${fmt} maps into OUT_EXTS`);
  }
  // lossy quality applies to jpg/jpeg/webp whenever those suffixes appear
  for (const e of qualityExts()) {
    assert.ok(IMAGE_EXTS.includes(e), `${e} is a known input suffix`);
    assert.ok(!e.endsWith(".png") && !e.endsWith(".bmp") && !e.endsWith(".gif"));
  }
});

test("bmp header is a valid 24-bit BITMAPINFOHEADER", async () => {
  const blob = canvasToBmp(fakeCanvas(2, 2, new Array(16).fill(0)));
  const buf = Buffer.from(await blob.arrayBuffer());
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  assert.equal(blob.type, "image/bmp");
  assert.equal(buf.subarray(0, 2).toString("latin1"), "BM");
  assert.equal(dv.getUint32(2, true), buf.length);
  assert.equal(dv.getUint32(10, true), 54);
  assert.equal(dv.getUint32(14, true), 40);
  assert.equal(dv.getInt32(18, true), 2);
  assert.equal(dv.getInt32(22, true), 2);
  assert.equal(dv.getUint16(26, true), 1);
  assert.equal(dv.getUint16(28, true), 24);
  assert.equal(dv.getUint32(30, true), 0);
  assert.equal(dv.getUint32(34, true), buf.length - 54);
});

test("bmp rows are padded to 4 bytes and stored bottom-up in BGR", async () => {
  const w = 3;
  const h = 2;
  const rgba = [
    1, 2, 3, 255, 4, 5, 6, 255, 7, 8, 9, 255,
    10, 11, 12, 255, 13, 14, 15, 255, 16, 17, 18, 255,
  ];
  const buf = Buffer.from(await canvasToBmp(fakeCanvas(w, h, rgba)).arrayBuffer());
  const rowBytes = (w * 3 + 3) & ~3;
  assert.equal(rowBytes, 12);
  assert.equal(buf.length, 54 + rowBytes * h);
  const firstRow = buf.subarray(54, 54 + w * 3);
  assert.deepEqual([...firstRow], [12, 11, 10, 15, 14, 13, 18, 17, 16]);
  assert.deepEqual([...buf.subarray(54 + w * 3, 54 + rowBytes)], [0, 0, 0]);
  const secondRow = buf.subarray(54 + rowBytes, 54 + rowBytes + w * 3);
  assert.deepEqual([...secondRow], [3, 2, 1, 6, 5, 4, 9, 8, 7]);
});

function installCanvasEnv(t, { bitmapW = 100, bitmapH = 50, failDecode = false, blobNull = false } = {}) {
  const state = { canvases: [], closed: 0, bitmapError: null };
  const origDoc = globalThis.document;
  const origCreate = globalThis.createImageBitmap;
  globalThis.document = {
    createElement(tag) {
      assert.equal(tag, "canvas");
      const calls = [];
      const ctx = {
        imageSmoothingQuality: "low",
        drawImage(...a) {
          calls.push(["drawImage", ...a]);
        },
        getImageData(x, y, w2, h2) {
          const data = new Uint8ClampedArray(w2 * h2 * 4);
          for (let i = 0; i < data.length; i += 4) {
            data[i] = (i + 1) % 256;
            data[i + 1] = (i + 2) % 256;
            data[i + 2] = (i + 3) % 256;
            data[i + 3] = 255;
          }
          return { data, width: w2, height: h2 };
        },
        _calls: calls,
      };
      const cv = {
        width: 0,
        height: 0,
        _ctx: ctx,
        _toBlobCalls: [],
        getContext(kind) {
          assert.equal(kind, "2d");
          return ctx;
        },
        toBlob(cb, type, quality) {
          cv._toBlobCalls.push({ type, quality });
          if (blobNull) cb(null);
          else cb(new Blob([new Uint8Array([7])], { type: type || "image/png" }));
        },
      };
      state.canvases.push(cv);
      return cv;
    },
  };
  globalThis.createImageBitmap = async () => {
    if (failDecode) throw new Error("decode failed");
    return {
      width: bitmapW,
      height: bitmapH,
      close() {
        state.closed += 1;
      },
    };
  };
  t.after(() => {
    globalThis.document = origDoc;
    if (origCreate === undefined) delete globalThis.createImageBitmap;
    else globalThis.createImageBitmap = origCreate;
  });
  return state;
}

test("loadImageBitmap wraps decode failures as AppError", async (t) => {
  const state = installCanvasEnv(t, { failDecode: true });
  await assert.rejects(
    () => loadImageBitmap({ name: "photo.png" }),
    (e) => {
      assert.equal(e.label, "图片处理失败");
      assert.match(e.detail, /无法读取图片: photo\.png/);
      return true;
    },
  );
  await assert.rejects(() => loadImageBitmap({}), /无法读取图片: /);
  assert.equal(state.closed, 0);
});

test("convertImage scales to maxWidth and converts to BMP", async (t) => {
  const state = installCanvasEnv(t, { bitmapW: 400, bitmapH: 200 });
  const out = await convertImage({ name: "shot.final.png" }, { format: "bmp", maxWidth: 100 });
  assert.equal(out.filename, "shot.final.bmp");
  assert.equal(out.width, 100);
  assert.equal(out.height, 50);
  assert.equal(out.blob.type, "image/bmp");
  assert.equal(state.closed, 1, "bitmap released");
  assert.equal(state.canvases.length, 1);
  const draw = state.canvases[0]._ctx._calls[0];
  assert.deepEqual(draw.slice(1).slice(-2), [100, 50]);
});

test("convertImage PNG omits quality; JPG clamps quality into 0..1", async (t) => {
  const state = installCanvasEnv(t);
  const png = await convertImage({ name: "a.png" }, { format: "PNG" });
  assert.equal(png.filename, "a.png");
  assert.equal(png.blob.type, "image/png");
  assert.equal(state.canvases[0]._toBlobCalls[0].quality, undefined);
  const jpg = await convertImage({ name: "b.jpg" }, { format: "jpg", quality: 200 });
  assert.equal(jpg.filename, "b.jpg");
  assert.equal(state.canvases[1]._toBlobCalls[0].type, "image/jpeg");
  assert.equal(state.canvases[1]._toBlobCalls[0].quality, 1);
  const webp = await convertImage({ name: "c.webp" }, { format: "WebP", quality: -5 });
  assert.equal(state.canvases[2]._toBlobCalls[0].quality, 0.01);
});

test("convertImage defaults format to PNG and names bare inputs", async (t) => {
  installCanvasEnv(t);
  const out = await convertImage({}, {});
  assert.equal(out.filename, "image.png");
  assert.equal(out.blob.type, "image/png");
  assert.equal(out.width, 100);
  assert.equal(out.height, 50);
});

test("convertImage rejects when canvas.toBlob yields nothing", async (t) => {
  installCanvasEnv(t, { blobNull: true });
  await assert.rejects(() => convertImage({ name: "x.png" }, { format: "png" }), /保存失败/);
});

test("convertImage encodes the GIF branch as animation/gif", async (t) => {
  installCanvasEnv(t, { bitmapW: 4, bitmapH: 4 });
  const out = await convertImage({ name: "anim.gif" }, { format: "GIF" });
  assert.equal(out.filename, "anim.gif");
  assert.equal(out.blob.type, "image/gif");
  const bytes = new Uint8Array(await out.blob.arrayBuffer());
  assert.equal(String.fromCharCode(...bytes.slice(0, 6)), "GIF89a");
});
