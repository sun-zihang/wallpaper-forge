import test from "node:test";
import assert from "node:assert/strict";
import { extractEmbedded } from "../lib/we_tex.js";

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
