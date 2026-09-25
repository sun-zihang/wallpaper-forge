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

test("garbage png carved once", () => {
  const data = new Uint8Array(64);
  data.set(new TextEncoder().encode("PKGM0019"), 0);
  data.fill(0x11, 8);
  data.set(new TextEncoder().encode("\x89PNG\r\n\x1a\n"), 16);
  data.set(new TextEncoder().encode("IEND"), 40);
  const { files } = extractMpkg(data);
  const pngs = files.filter((f) => f.name.endsWith(".png"));
  assert.equal(pngs.length, 1);
});

test("path-traversal pkg falls through without escaping names", () => {
  // extractPkg rejects "../" — extractMpkg must fall through to carving
  // and never return a name containing ".."
  const enc = new TextEncoder();
  const header = enc.encode("PKGM0014");
  const name = enc.encode("../escape.txt");
  const blob = enc.encode("pwned");
  const parts = [];
  const pushU32 = (v) => {
    const b = new Uint8Array(4);
    new DataView(b.buffer).setUint32(0, v, true);
    parts.push(b);
  };
  pushU32(header.length);
  parts.push(header);
  pushU32(1);
  pushU32(name.length);
  parts.push(name);
  pushU32(0);
  pushU32(blob.length);
  parts.push(blob);
  // pad to >= 16 total (already is)
  const total = parts.reduce((s, p) => s + p.length, 0);
  const data = new Uint8Array(total);
  let p = 0;
  for (const part of parts) {
    data.set(part, p);
    p += part.length;
  }
  // May throw (no carveable media) or return carved files — but never ".."
  try {
    const { files } = extractMpkg(data);
    for (const f of files) {
      assert.ok(!f.name.includes(".."), `unsafe name: ${f.name}`);
      assert.ok(!/^[a-zA-Z]:/.test(f.name), `drive letter name: ${f.name}`);
    }
  } catch (e) {
    // expected when nothing carveable
    assert.match(String(e), /MPKG|无法/);
  }
});

test("too-small buffer rejected", () => {
  assert.throws(() => extractMpkg(new Uint8Array(8)), /过小/);
});

test("invalid mp4 box size falls back to a bounded slice", () => {
  const enc = new TextEncoder();
  const data = new Uint8Array(200);
  data.fill(0x33);
  data.set(enc.encode("PKGM0014"), 0);
  // size field 0xFFFFFFFF is invalid → fallback slice(start, i + 4096)
  data.set([0xff, 0xff, 0xff, 0xff], 16);
  data.set(enc.encode("ftyp"), 20);
  data.set([0, 0, 0, 40], 96);
  data.set(enc.encode("ftyp"), 100);
  const { files } = extractMpkg(data);
  assert.equal(files.length, 1, "second ftyp is contained in the first slice");
  assert.equal(files[0].name, "extracted_01.mp4");
  assert.equal(files[0].blob.length, 184, "fallback slice covers the tail");
});

test("two non-overlapping valid mp4 boxes both survive dedup", () => {
  const enc = new TextEncoder();
  const data = new Uint8Array(200);
  data.fill(0x33);
  data.set(enc.encode("PKGM0014"), 0);
  data.set([0, 0, 0, 32], 16);
  data.set(enc.encode("ftyp"), 20);
  data.set([0, 0, 0, 40], 96);
  data.set(enc.encode("ftyp"), 100);
  const { files } = extractMpkg(data);
  assert.equal(files.length, 2);
  assert.deepEqual(files.map((f) => f.name), ["extracted_01.mp4", "extracted_02.mp4"]);
  assert.deepEqual(files.map((f) => f.blob.length), [40, 32], "kept longest-first");
});

test("standalone PNG carving finds multiple embedded signatures with IEND", () => {
  const enc = new TextEncoder();
  const PNG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  const data = new Uint8Array(120);
  data.fill(0x33);
  data.set(enc.encode("PKGM0019"), 0);
  // first png: declared length 10 (LE) makes extractEmbedded discard it (<16 bytes)
  data.set([10, 0, 0, 0], 36);
  data.set(PNG, 40);
  data.set(enc.encode("IEND"), 48);
  // second png proves the scan advances past the previous signature
  data.set([10, 0, 0, 0], 66);
  data.set(PNG, 70);
  data.set(enc.encode("IEND"), 78);
  const { files } = extractMpkg(data);
  const pngs = files.filter((f) => f.name.endsWith(".png"));
  assert.equal(pngs.length, 2);
  assert.deepEqual(pngs.map((f) => f.name), ["extracted_01.png", "extracted_02.png"]);
});

test("valid pkg with a .tex entry is unpacked through extractTex", () => {
  const enc = new TextEncoder();
  const header = enc.encode("PKGM0014");
  const name = enc.encode("scene.tex");
  const blob = enc.encode("no embedded media here");
  const parts = [];
  const pushU32 = (v) => {
    const b = new Uint8Array(4);
    new DataView(b.buffer).setUint32(0, v, true);
    parts.push(b);
  };
  pushU32(header.length);
  parts.push(header);
  pushU32(1);
  pushU32(name.length);
  parts.push(name);
  pushU32(0);
  pushU32(blob.length);
  parts.push(blob);
  const total = parts.reduce((s, p) => s + p.length, 0);
  const data = new Uint8Array(total);
  let p = 0;
  for (const part of parts) {
    data.set(part, p);
    p += part.length;
  }
  const { files } = extractMpkg(data);
  assert.equal(files.length, 1);
  assert.equal(files[0].name, "scene.tex");
  assert.equal(new TextDecoder().decode(files[0].blob), "no embedded media here");
});
