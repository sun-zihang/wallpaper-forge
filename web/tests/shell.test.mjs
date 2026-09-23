// web/tests/shell.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { WEB_VERSION } from "../version.js";

test("web version semver-ish", () => {
  assert.match(WEB_VERSION, /^\d+\.\d+\.\d+$/);
});
