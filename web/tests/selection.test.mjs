// web/tests/selection.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { validateSelection } from "../lib/selection.js";

const f = (name, size = 1024) => ({ name, size });

test("accepts matching extensions case-insensitively", () => {
  const r = validateSelection([f("a.PNG"), f("b.JpG")], { extensions: [".png", ".jpg"] });
  assert.equal(r.ok, true);
  assert.equal(r.files.length, 2);
});

test("rejects wrong extensions and reports every offender", () => {
  const r = validateSelection([f("a.png"), f("b.txt"), f("c.exe")], { extensions: [".png"] });
  assert.equal(r.ok, false);
  assert.equal(r.errors.length, 2);
  assert.deepEqual(r.errors.map((e) => e.name), ["b.txt", "c.exe"]);
  assert.match(r.errors[0].reason, /不支持的文件类型/);
  assert.equal(r.files.length, 1);
});

test("rejects empty files before extension checks", () => {
  const r = validateSelection([f("empty.png", 0)], { extensions: [".png"] });
  assert.equal(r.ok, false);
  assert.equal(r.errors[0].reason, "文件为空");
});

test("rejects files over the size cap with an MB message", () => {
  const r = validateSelection([f("big.mp4", 101 * 1024 * 1024)], { maxSize: 100 * 1024 * 1024 });
  assert.equal(r.ok, false);
  assert.match(r.errors[0].reason, /100MB/);
});

test("without an extension filter any type passes, but empty files are still rejected", () => {
  const okRes = validateSelection([f("x.bin"), f("y.dat")]);
  assert.equal(okRes.ok, true);
  assert.equal(okRes.files.length, 2);
  const emptyRes = validateSelection([f("z.bin", 0)]);
  assert.equal(emptyRes.ok, false);
  assert.equal(emptyRes.errors[0].reason, "文件为空");
});

test("handles missing name and null entries without throwing", () => {
  const r = validateSelection([null, { size: 10 }, { name: "ok.png", size: 10 }], {
    extensions: [".png"],
  });
  assert.equal(r.ok, false);
  assert.equal(r.errors.length, 2);
  assert.equal(r.files.length, 1);
  assert.equal(r.files[0].name, "ok.png");
});
