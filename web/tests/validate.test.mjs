// web/tests/validate.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  MAX_IMAGE_DIM,
  assertImageResolution,
  pngHeaderSize,
  sniffImage,
  sniffVideo,
  validateImageBytes,
  validateImageFile,
  validateVideoBytes,
  validateVideoFile,
} from "../lib/validate.js";

function bytes(list) {
  return new Uint8Array(list);
}

test("sniffImage recognises each supported image container", () => {
  assert.equal(sniffImage(bytes([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 1, 2])), "png");
  assert.equal(sniffImage(bytes([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10])), "jpeg");
  assert.equal(sniffImage(bytes([0x47, 0x49, 0x46, 0x38, 0x39, 0x61])), "gif");
  assert.equal(sniffImage(bytes([0x42, 0x4d, 0x00, 0x00])), "bmp");
  assert.equal(
    sniffImage(bytes([0x52, 0x49, 0x46, 0x46, 0x24, 0x00, 0x00, 0x00, 0x57, 0x45, 0x42, 0x50])),
    "webp",
  );
});

test("sniffImage rejects non-image and truncated headers", () => {
  assert.equal(sniffImage(bytes([0x3c, 0x21, 0x44, 0x4f])), null); // "<!DO" html
  assert.equal(sniffImage(bytes([0x50, 0x4b, 0x03, 0x04])), null); // zip
  assert.equal(sniffImage(bytes([])), null);
  assert.equal(sniffImage(bytes([0x89, 0x50, 0x4e, 0x47])), null); // truncated png
  assert.equal(sniffImage(bytes([0x52, 0x49, 0x46, 0x46, 0, 0, 0, 0, 0x41, 0x56, 0x49, 0x20])), null); // RIFF/AVI is not WEBP
});

test("pngHeaderSize reads IHDR dimensions big-endian", () => {
  const b = bytes([
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
    0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
    0x00, 0x00, 0x00, 0x64, 0x00, 0x00, 0x00, 0x32,
  ]);
  assert.deepEqual(pngHeaderSize(b), { width: 100, height: 50 });
  assert.equal(pngHeaderSize(bytes([0xff, 0xd8, 0xff])), null);
  assert.equal(pngHeaderSize(bytes([0x89, 0x50, 0x4e, 0x47])), null);
});

test("validateImageBytes accepts every supported type", () => {
  assert.equal(validateImageBytes(bytes([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), "a.png"), "png");
  assert.equal(validateImageBytes(bytes([0xff, 0xd8, 0xff, 0xe0]), "a.jpg"), "jpeg");
  assert.equal(validateImageBytes(bytes([0x47, 0x49, 0x46, 0x38]), "a.gif"), "gif");
  assert.equal(validateImageBytes(bytes([0x42, 0x4d]), "a.bmp"), "bmp");
  assert.equal(
    validateImageBytes(bytes([0x52, 0x49, 0x46, 0x46, 1, 2, 3, 4, 0x57, 0x45, 0x42, 0x50]), "a.webp"),
    "webp",
  );
});

test("validateImageBytes rejects files that are not images", () => {
  assert.throws(
    () => validateImageBytes(bytes([0x3c, 0x68, 0x74, 0x6d, 0x6c]), "evil.png"),
    (e) => e.label === "图片处理失败" && e.detail.includes("文件头无法识别"),
  );
  assert.throws(() => validateImageBytes(bytes([0x50, 0x4b, 0x03, 0x04]), "evil2.png"), /文件头无法识别/);
});

test("validateImageBytes rejects absurd PNG header dimensions", () => {
  const huge = [
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
    0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
    0x05, 0xf5, 0xe0, 0xff, 0x00, 0x00, 0x00, 0x32,
  ];
  assert.throws(
    () => validateImageBytes(bytes(huge), "bomb.png"),
    (e) => e.label === "图片处理失败" && e.detail.includes("图片尺寸异常") && e.detail.includes("99999999"),
  );
  const zero = [
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
    0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x32,
  ];
  assert.throws(() => validateImageBytes(bytes(zero), "zero.png"), /图片尺寸异常/);
});

test("assertImageResolution allows normal and 32K images but rejects beyond 16K", () => {
  assert.doesNotThrow(() => assertImageResolution(1920, 1080));
  assert.doesNotThrow(() => assertImageResolution(MAX_IMAGE_DIM, MAX_IMAGE_DIM));
  assert.throws(
    () => assertImageResolution(32768, 2160),
    (e) =>
      e.label === "图片处理失败" &&
      e.detail.includes("32768×2160") &&
      e.detail.includes("建议下载桌面版"),
  );
});

test("sniffVideo recognises ISO-BMFF and EBML containers", () => {
  const mp4 = bytes([0x00, 0x00, 0x00, 0x18, 0x66, 0x74, 0x79, 0x70, 0x6d, 0x70, 0x34, 0x32]);
  assert.equal(sniffVideo(mp4), "bmff");
  const webm = bytes([0x1a, 0x45, 0xdf, 0xa3, 0x01, 0x00, 0x00, 0x00]);
  assert.equal(sniffVideo(webm), "ebml");
  assert.equal(sniffVideo(bytes([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])), null);
  assert.equal(sniffVideo(bytes([0x66, 0x74, 0x79, 0x70])), null); // ftyp must sit at offset 4
  assert.equal(sniffVideo(bytes([])), null);
});

test("validateVideoBytes rejects non-video files", () => {
  assert.equal(validateVideoBytes(bytes([0x00, 0x00, 0x00, 0x18, 0x66, 0x74, 0x79, 0x70, 0x69, 0x73, 0x6f, 0x6d]), "a.mp4"), "bmff");
  assert.equal(validateVideoBytes(bytes([0x1a, 0x45, 0xdf, 0xa3]), "a.webm"), "ebml");
  assert.throws(
    () => validateVideoBytes(bytes([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), "fake.mp4"),
    (e) => e.label === "视频处理失败" && e.detail.includes("文件头无法识别"),
  );
});

function fakeFile(name, header) {
  return {
    name,
    slice: (a, b) => ({ arrayBuffer: async () => new Uint8Array(header.slice(a, b)).buffer }),
  };
}

test("validateImageFile reads the header via slice and validates", async () => {
  const png = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  assert.equal(await validateImageFile(fakeFile("a.png", png)), "png");
  await assert.rejects(
    () => validateImageFile(fakeFile("evil.png", [0x3c, 0x68, 0x74, 0x6d, 0x6c])),
    /文件头无法识别/,
  );
});

test("validateVideoFile reads the header via slice and validates", async () => {
  const mp4 = [0x00, 0x00, 0x00, 0x18, 0x66, 0x74, 0x79, 0x70, 0x6d, 0x70, 0x34, 0x32];
  assert.equal(await validateVideoFile(fakeFile("a.mp4", mp4)), "bmff");
  await assert.rejects(
    () => validateVideoFile(fakeFile("fake.mp4", [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])),
    /文件头无法识别/,
  );
});
