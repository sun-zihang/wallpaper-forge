import test from "node:test";
import assert from "node:assert/strict";
import { cropBoxValid, pastePos, POSITIONS } from "../lib/annotate.js";

test("crop validation matches desktop bounds rule", () => {
  assert.equal(cropBoxValid([0, 0, 32, 24], 64, 48), true);
  assert.equal(cropBoxValid([0, 0, 999, 999], 64, 48), false);
  assert.equal(cropBoxValid([10, 10, 10, 20], 64, 48), false);
});

test("paste position bottom_right", () => {
  const [x, y] = pastePos(100, 80, 10, 10, "bottom_right", 4);
  assert.equal(x, 100 - 10 - 4);
  assert.equal(y, 80 - 10 - 4);
});

test("paste position center", () => {
  assert.deepEqual(pastePos(100, 80, 10, 10, "center", 4), [45, 35]);
});

test("positions set same as desktop", () => {
  assert.deepEqual([...POSITIONS].sort(), [
    "bottom_left", "bottom_right", "center", "top_left", "top_right",
  ]);
});
