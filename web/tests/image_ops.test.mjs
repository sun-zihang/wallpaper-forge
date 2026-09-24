import test from "node:test";
import assert from "node:assert/strict";
import { OUT_EXTS, outputExtFor, qualityExts, canvasToBmp } from "../lib/image_ops.js";

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
  assert.ok(OUT_EXTS.includes(".webp"));
  assert.ok(OUT_EXTS.includes(".bmp"));
});

test("quality only for lossy", () => {
  assert.ok(qualityExts().has(".jpg"));
  assert.ok(qualityExts().has(".webp"));
  assert.ok(!qualityExts().has(".png"));
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
