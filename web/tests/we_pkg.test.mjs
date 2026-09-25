import test from "node:test";
import assert from "node:assert/strict";
import { readPkgIndex, extractPkg } from "../lib/we_pkg.js";

function buildPkg(files, magic = "PKGV0005") {
  const enc = new TextEncoder();
  const names = Object.keys(files);
  const header = enc.encode(magic);
  const blobs = names.map((n) => files[n]);
  const pre = 4 + header.length + 4 + names.reduce((s, n) => s + 4 + enc.encode(n).length + 8, 0);
  const parts = [];
  const pushU32 = (v) => {
    const b = new Uint8Array(4);
    new DataView(b.buffer).setUint32(0, v, true);
    parts.push(b);
  };
  pushU32(header.length);
  parts.push(header);
  pushU32(names.length);
  let off = 0;
  names.forEach((n, i) => {
    const nb = enc.encode(n);
    pushU32(nb.length);
    parts.push(nb);
    pushU32(off);
    pushU32(blobs[i].length);
    off += blobs[i].length;
  });
  const indexLen = parts.reduce((s, p) => s + p.length, 0);
  assert.equal(indexLen, pre);
  parts.push(...blobs);
  const total = parts.reduce((s, p) => s + p.length, 0);
  const out = new Uint8Array(total);
  let p = 0;
  for (const part of parts) {
    out.set(part, p);
    p += part.length;
  }
  return out;
}

test("read index", () => {
  const pkg = buildPkg({ "a.txt": new TextEncoder().encode("hello") });
  const { magic, entries } = readPkgIndex(pkg);
  assert.ok(magic.startsWith("PKGV"));
  assert.equal(entries[0].name, "a.txt");
  assert.equal(entries[0].length, 5);
});

test("extract payload", () => {
  const pkg = buildPkg({ "a.txt": new TextEncoder().encode("hello") });
  const { files } = extractPkg(pkg);
  assert.equal(new TextDecoder().decode(files[0].blob), "hello");
  assert.equal(files[0].name, "a.txt");
});

test("extract rejects path traversal entries", () => {
  const pkg = buildPkg({ "../escape.txt": new TextEncoder().encode("pwned") });
  assert.throws(() => extractPkg(pkg), /非法路径/);
});

test("extract rejects nested parent segments", () => {
  const pkg = buildPkg({ "sub/../../out.txt": new TextEncoder().encode("x") });
  assert.throws(() => extractPkg(pkg), /非法路径/);
});

test("extract rejects drive-letter absolute paths", () => {
  const pkg = buildPkg({ "C:/Windows/evil.txt": new TextEncoder().encode("x") });
  assert.throws(() => extractPkg(pkg), /非法路径/);
});

test("extract rejects backslash drive-letter entries", () => {
  const pkg = buildPkg({ "C:\\Windows\\evil.txt": new TextEncoder().encode("x") });
  assert.throws(() => extractPkg(pkg), /非法路径/);
});

test("zero entries parses empty", () => {
  const pkg = buildPkg({});
  const { entries } = readPkgIndex(pkg);
  assert.equal(entries.length, 0);
});

test("backslash names normalized to forward slash", () => {
  const pkg = buildPkg({ "sub\\nested\\a.txt": new TextEncoder().encode("x") });
  const { entries } = readPkgIndex(pkg);
  assert.equal(entries[0].name, "sub/nested/a.txt");
});

test("oversized header length rejected", () => {
  const data = new Uint8Array(8);
  new DataView(data.buffer).setUint32(0, 0xffffff, true);
  data.set([0x58, 0x58, 0x58, 0x58], 4);
  assert.throws(() => readPkgIndex(data), /头部长度异常/);
});

test("absurd file count rejected", () => {
  const header = new TextEncoder().encode("PKGV0005");
  const data = new Uint8Array(4 + header.length + 4);
  const dv = new DataView(data.buffer);
  dv.setUint32(0, header.length, true);
  data.set(header, 4);
  dv.setUint32(4 + header.length, 2_000_000, true);
  assert.throws(() => readPkgIndex(data), /文件数异常/);
});

test("truncated entry rejected", () => {
  const header = new TextEncoder().encode("PKGV0005");
  const parts = [];
  const pushU32 = (v) => {
    const b = new Uint8Array(4);
    new DataView(b.buffer).setUint32(0, v, true);
    parts.push(b);
  };
  pushU32(header.length);
  parts.push(header);
  pushU32(1);
  pushU32(100);
  parts.push(new TextEncoder().encode("ab"));
  const total = parts.reduce((s, p) => s + p.length, 0);
  const data = new Uint8Array(total);
  let p = 0;
  for (const part of parts) {
    data.set(part, p);
    p += part.length;
  }
  assert.throws(() => readPkgIndex(data), /索引损坏/);
});

test("tiny buffer rejected", () => {
  assert.throws(() => readPkgIndex(new Uint8Array([1, 2, 3])), /过小/);
});

test("out-of-bounds entry offset rejected", () => {
  const header = new TextEncoder().encode("PKGV0005");
  const name = new TextEncoder().encode("a.txt");
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
  pushU32(0x7fff0000);
  pushU32(0x7fff0000);
  const total = parts.reduce((s, p) => s + p.length, 0);
  const data = new Uint8Array(total);
  let p = 0;
  for (const part of parts) {
    data.set(part, p);
    p += part.length;
  }
  assert.throws(() => extractPkg(data), /条目越界/);
});

test("empty index extracts nothing", () => {
  const pkg = buildPkg({});
  const { files } = extractPkg(pkg);
  assert.equal(files.length, 0);
});

test("oversized non-PKG header magic rejected", () => {
  const enc = new TextEncoder();
  const data = new Uint8Array(1200);
  new DataView(data.buffer).setUint32(0, 1100, true);
  data.set(enc.encode("ZZZZ".padEnd(1100, "A")), 4);
  assert.throws(() => readPkgIndex(data), (e) => {
    assert.equal(e.label, "PKG 解包失败");
    assert.match(e.detail, /头部: ZZZZ/);
    return true;
  });
  // headerLen <= 1024 with a non-PKG magic falls through (short probes allowed)
  const short = new Uint8Array(64);
  new DataView(short.buffer).setUint32(0, 8, true);
  short.set(enc.encode("PROBE001"), 4);
  const { magic } = readPkgIndex(short);
  assert.equal(magic, "PROBE001");
});
