import test from "node:test";
import assert from "node:assert/strict";
import { OUT_EXTS, outputExtFor, qualityExts } from "../lib/image_ops.js";

test("output ext mapping", () => {
  assert.equal(outputExtFor("PNG"), ".png");
  assert.equal(outputExtFor("JPG"), ".jpg");
  assert.ok(OUT_EXTS.includes(".webp"));
});

test("quality only for lossy", () => {
  assert.ok(qualityExts().has(".jpg"));
  assert.ok(qualityExts().has(".webp"));
  assert.ok(!qualityExts().has(".png"));
});
