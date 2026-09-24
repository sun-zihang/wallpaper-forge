// web/tests/progress.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { batchPct } from "../lib/progress.js";

test("single file spans the whole bar", () => {
  assert.equal(batchPct(0, 0, 1), 0);
  assert.equal(batchPct(0, 50, 1), 50);
  assert.equal(batchPct(0, 100, 1), 100);
});

test("multi-file batch gives each file an equal span", () => {
  assert.equal(batchPct(0, 0, 4), 0);
  assert.equal(batchPct(0, 100, 4), 25);
  assert.equal(batchPct(1, 0, 4), 25);
  assert.equal(batchPct(1, 50, 4), 38);
  assert.equal(batchPct(3, 100, 4), 100);
});

test("batchPct clamps out-of-range and invalid input", () => {
  assert.equal(batchPct(-5, 0, 4), 0);
  assert.equal(batchPct(0, -20, 4), 0);
  assert.equal(batchPct(0, 500, 4), 25);
  assert.equal(batchPct(0, 0, 0), 0);
  assert.equal(batchPct(1, 100, 0), 100);
  assert.equal(batchPct(2, NaN, 4), 50);
});
