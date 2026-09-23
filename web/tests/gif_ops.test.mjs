// web/tests/gif_ops.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  stepIndexKept,
  mergeOrder,
  GIFUCT_ESM_URL,
  decompressFramePatch,
} from "../lib/gif_ops.js";

test("split step keeps first frame at step>=1", () => {
  assert.deepEqual([0, 1, 2, 3].filter((i) => stepIndexKept(i, 2)), [0, 2]);
  assert.deepEqual([0, 1, 2].filter((i) => stepIndexKept(i, 1)), [0, 1, 2]);
});

test("merge reverse order", () => {
  assert.deepEqual(mergeOrder(["a", "b"], true), ["b", "a"]);
  assert.deepEqual(mergeOrder(["a", "b"], false), ["a", "b"]);
});

test("gifuct is pinned to the ESM bundle (2.1.2 has no dist/ UMD build)", () => {
  assert.equal(GIFUCT_ESM_URL, "https://cdn.jsdelivr.net/npm/gifuct-js@2.1.2/+esm");
  assert.ok(!/\/dist\//.test(GIFUCT_ESM_URL));
});

test("decompressFramePatch calls gifuct(frame, gct, buildImagePatch) in order", () => {
  const calls = [];
  const gct = { exists: true };
  const frame = { image: { descriptor: { width: 2, height: 2 } } };
  const lib = {
    decompressFrame(...args) {
      calls.push(args);
      return { patch: new Uint8Array(16) };
    },
  };
  const parsed = { gct };
  const patch = decompressFramePatch(lib, parsed, frame);
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], frame);
  assert.equal(calls[0][1], gct);
  assert.equal(calls[0][2], true);
  assert.ok(patch && patch.patch);
});

test("decompressFramePatch returns null for frames gifuct cannot decompress", () => {
  const lib = { decompressFrame: () => undefined };
  assert.equal(decompressFramePatch(lib, { gct: null }, {}), null);
  const noPatch = { decompressFrame: () => ({ dims: {} }) };
  assert.equal(decompressFramePatch(noPatch, { gct: null }, {}), null);
});

