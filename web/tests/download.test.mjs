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
