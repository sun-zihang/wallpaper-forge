import test from "node:test";
import assert from "node:assert/strict";
import { friendlyError, AppError } from "../lib/errors.js";

test("friendlyError maps AppError", () => {
  assert.equal(friendlyError(new AppError("图片处理失败", "无法读取图片")), "图片处理失败：无法读取图片");
});

test("friendlyError unknown", () => {
  assert.match(friendlyError(new Error("boom")), /未知错误/);
});
