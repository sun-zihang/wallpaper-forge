// web/tests/download.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { baseName, stem } from "../lib/download.js";

test("path helpers normalise windows separators", () => {
  assert.equal(baseName("C:\\a\\b\\c.png"), "c.png");
  assert.equal(stem("C:\\a\\b\\c.png"), "c");
  assert.equal(stem("noext"), "noext");
  assert.equal(stem(".hidden"), ".hidden");
});

test("stem keeps only the final extension", () => {
  assert.equal(stem("archive.tar.gz"), "archive.tar");
  assert.equal(stem("a.b.c"), "a.b");
  assert.equal(stem("trailing."), "trailing");
  assert.equal(baseName("/only/one/"), "");
});
