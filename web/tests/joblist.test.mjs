import test from "node:test";
import assert from "node:assert/strict";

// Pure status text table (extracted for testability)
import { STATUS_TEXT } from "../lib/joblist.js";

test("status text matches desktop", () => {
  assert.equal(STATUS_TEXT.pending, "等待");
  assert.equal(STATUS_TEXT.running, "处理中");
  assert.equal(STATUS_TEXT.done, "完成");
  assert.equal(STATUS_TEXT.failed, "失败");
  assert.equal(STATUS_TEXT.cancelled, "已取消");
});

test("status table covers exactly the five job states", () => {
  assert.deepEqual(
    Object.keys(STATUS_TEXT).sort(),
    ["cancelled", "done", "failed", "pending", "running"],
  );
  for (const v of Object.values(STATUS_TEXT)) {
    assert.ok(typeof v === "string" && v.length > 0);
  }
});
