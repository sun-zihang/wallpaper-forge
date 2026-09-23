// web/tests/gif_ops.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { stepIndexKept, mergeOrder } from "../lib/gif_ops.js";

test("split step keeps first frame at step>=1", () => {
  assert.deepEqual([0, 1, 2, 3].filter((i) => stepIndexKept(i, 2)), [0, 2]);
  assert.deepEqual([0, 1, 2].filter((i) => stepIndexKept(i, 1)), [0, 1, 2]);
});

test("merge reverse order", () => {
  assert.deepEqual(mergeOrder(["a", "b"], true), ["b", "a"]);
  assert.deepEqual(mergeOrder(["a", "b"], false), ["a", "b"]);
});
