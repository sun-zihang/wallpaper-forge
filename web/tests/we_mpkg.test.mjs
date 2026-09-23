import test from "node:test";
import assert from "node:assert/strict";
import { isMpkg, extractMpkg } from "../lib/we_mpkg.js";

test("isMpkg magic", () => {
  assert.equal(isMpkg(new TextEncoder().encode("PKGM0014xxxxxxxx")), true);
  assert.equal(isMpkg(new TextEncoder().encode("XXXX")), false);
});

test("carve mp4 from garbage-with-ftyp", () => {
  const ftyp = new Uint8Array(32);
  const dv = new DataView(ftyp.buffer);
  dv.setUint32(0, 32, false);
  ftyp.set(new TextEncoder().encode("ftyp"), 4);
  ftyp.set(new TextEncoder().encode("mp42"), 8);
  const moov = new Uint8Array(16);
  new DataView(moov.buffer).setUint32(0, 16, false);
  moov.set(new TextEncoder().encode("moov"), 4);
  const data = new Uint8Array(8 + 32 + 16 + 8);
  data.set(new TextEncoder().encode("PKGM0014"), 0);
  data.set(ftyp, 8);
  data.set(moov, 40);
  const { files } = extractMpkg(data);
  assert.ok(files.length >= 1);
  assert.ok(files.some((f) => f.name.endsWith(".mp4")));
});

test("garbage raises Chinese", () => {
  const data = new Uint8Array(116);
  data.set(new TextEncoder().encode("PKGM0019"), 0);
  data.fill(0x11, 8);
  assert.throws(() => extractMpkg(data), /MPKG|无法/);
});
