import test from "node:test";
import assert from "node:assert/strict";
import { extractEmbedded, extractTex } from "../lib/we_tex.js";

const PNG_SIG = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

function concatBytes(...parts) {
  const total = parts.reduce((s, p) => s + p.length, 0);
  const out = new Uint8Array(total);
  let p = 0;
  for (const part of parts) {
    out.set(part, p);
    p += part.length;
  }
  return out;
}

function u32leBytes(v) {
  const b = new Uint8Array(4);
  new DataView(b.buffer).setUint32(0, v, true);
  return b;
}

test("embedded png with length prefix", () => {
  const png = new Uint8Array([...new TextEncoder().encode("\x89PNG\r\n\x1a\n"), ...new Uint8Array(10)]);
  // build: 16 zeros + u32le(len) + png
  const len = new Uint8Array(4);
  new DataView(len.buffer).setUint32(0, png.length, true);
  const blob = new Uint8Array(16 + 4 + png.length + 8);
  blob.set(len, 16);
  blob.set(png, 20);
  const { ext } = extractEmbedded(blob);
  assert.equal(ext, ".png");
});

test("embedded mp4 ftyp", () => {
  const ftyp = new Uint8Array(20);
  const dv = new DataView(ftyp.buffer);
  dv.setUint32(0, 20, false);
  ftyp.set(new TextEncoder().encode("ftyp"), 4);
  ftyp.set(new TextEncoder().encode("isom"), 8);
  const blob = new Uint8Array(32 + 20 + 16);
  blob.set(ftyp, 32);
  const { ext } = extractEmbedded(blob);
  assert.equal(ext, ".mp4");
});

test("embedded webp RIFF", () => {
  const webp = new Uint8Array(20);
  webp.set(new TextEncoder().encode("RIFF"), 0);
  new DataView(webp.buffer).setUint32(4, 12, true);
  webp.set(new TextEncoder().encode("WEBP"), 8);
  webp.set(new TextEncoder().encode("VP8 "), 12);
  const blob = new Uint8Array(16 + 4 + webp.length + 8);
  new DataView(blob.buffer).setUint32(16, webp.length, true);
  blob.set(webp, 20);
  const { ext } = extractEmbedded(blob);
  assert.equal(ext, ".webp");
});

test("no payload returns null ext", () => {
  const { ext, payload } = extractEmbedded(new Uint8Array(64));
  assert.equal(ext, null);
  assert.equal(payload, null);
});

test("embedded jpeg trims at EOI", () => {
  // payload must be >= 16 bytes (extractEmbedded rejects shorter)
  const jpg = new Uint8Array([
    0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xff, 0xd9,
  ]);
  const blob = new Uint8Array(8 + 4 + jpg.length + 8);
  new DataView(blob.buffer).setUint32(8, jpg.length, true);
  blob.set(jpg, 12);
  const { ext, payload } = extractEmbedded(blob);
  assert.equal(ext, ".jpg");
  assert.equal(payload[0], 0xff);
  assert.equal(payload[1], 0xd8);
  assert.equal(payload[payload.length - 2], 0xff);
  assert.equal(payload[payload.length - 1], 0xd9);
});

test("prefers mp4 over png when both present", () => {
  const png = concatBytes(PNG_SIG, new TextEncoder().encode("IHDR"), new Uint8Array(13), new TextEncoder().encode("IEND"), new Uint8Array(4));
  const ftyp = new Uint8Array(20);
  const dv = new DataView(ftyp.buffer);
  dv.setUint32(0, 20, false);
  ftyp.set(new TextEncoder().encode("ftyp"), 4);
  ftyp.set(new TextEncoder().encode("isom"), 8);
  const blob = concatBytes(png, new Uint8Array(16), ftyp, new Uint8Array(16));
  const { ext } = extractEmbedded(blob);
  assert.equal(ext, ".mp4");
});

test("prefers larger same-type payload", () => {
  const small = concatBytes(PNG_SIG, new TextEncoder().encode("IEND"), new Uint8Array(4));
  const big = concatBytes(PNG_SIG, new TextEncoder().encode("IHDR"), new Uint8Array(40), new TextEncoder().encode("IEND"), new Uint8Array(4));
  const blob = concatBytes(
    new Uint8Array(8),
    u32leBytes(small.length),
    small,
    new Uint8Array(8),
    u32leBytes(big.length),
    big,
  );
  const { ext, payload } = extractEmbedded(blob);
  assert.equal(ext, ".png");
  assert.equal(payload.length, big.length);
});

test("extractTex names with baseName", () => {
  const png = concatBytes(PNG_SIG, new TextEncoder().encode("IEND"), new Uint8Array(4));
  const blob = concatBytes(new Uint8Array(8), u32leBytes(png.length), png, new Uint8Array(8));
  const got = extractTex(blob, "custom_base");
  assert.equal(got.name, "custom_base.png");
  assert.equal(got.blob.length, png.length);
});

test("extractTex falls back to .tex baseName", () => {
  const got = extractTex(new Uint8Array(64), "keep.old");
  assert.equal(got.name, "keep.old.tex");
  assert.equal(got.blob.length, 64);
});
