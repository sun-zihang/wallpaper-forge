// web/tests/we_detect.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { detectKind } from "../lib/we_detect.js";

test("detectKind maps the three Wallpaper Engine extensions", () => {
  assert.equal(detectKind("scene.pkg"), "pkg");
  assert.equal(detectKind("wall.tex"), "tex");
  assert.equal(detectKind("bundle.mpkg"), "mpkg");
});

test("detectKind is case-insensitive", () => {
  assert.equal(detectKind("SCENE.PKG"), "pkg");
  assert.equal(detectKind("Wall.TEX"), "tex");
  assert.equal(detectKind("BUNDLE.MPKG"), "mpkg");
});

test("detectKind returns null for unknown or empty names", () => {
  assert.equal(detectKind("photo.png"), null);
  assert.equal(detectKind("archive.zip"), null);
  assert.equal(detectKind(""), null);
  assert.equal(detectKind(null), null);
});
