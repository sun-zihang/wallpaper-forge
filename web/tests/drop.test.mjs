// web/tests/drop.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { filterDropped } from "../lib/drop.js";

const f = (name) => ({ name, size: 10 });

test("keeps everything when no extension filter is given", () => {
  const files = [f("a.bin"), f("b.txt")];
  const { kept, rejected } = filterDropped(files);
  assert.deepEqual(kept.map((x) => x.name), ["a.bin", "b.txt"]);
  assert.deepEqual(rejected, []);
});

test("splits keep/reject on extension, case-insensitively", () => {
  const { kept, rejected } = filterDropped(
    [f("a.PKG"), f("b.tex"), f("c.mp4"), f("d")],
    [".pkg", ".tex", ".mpkg"]
  );
  assert.deepEqual(kept.map((x) => x.name), ["a.PKG", "b.tex"]);
  assert.deepEqual(rejected.map((x) => x.name), ["c.mp4", "d"]);
});

test("handles empty and missing input", () => {
  assert.deepEqual(filterDropped([], [".png"]), { kept: [], rejected: [] });
  assert.deepEqual(filterDropped(null, [".png"]), { kept: [], rejected: [] });
});
