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
  assert.equal(detectKind(undefined), null);
  assert.equal(detectKind(123), null);
});

test("detectKind only matches trailing extension, not substring", () => {
  assert.equal(detectKind("scene.pkg.exe"), null);
  assert.equal(detectKind("pkg"), null);
  assert.equal(detectKind("x.textr"), null);
  assert.equal(detectKind("/path/to/wall.pkg"), "pkg");
  assert.equal(detectKind("C:\\wall\\wall.TEX"), "tex");
});
