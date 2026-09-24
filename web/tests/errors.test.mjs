import test from "node:test";
import assert from "node:assert/strict";
import { friendlyError, AppError } from "../lib/errors.js";

test("friendlyError maps AppError", () => {
  assert.equal(friendlyError(new AppError("图片处理失败", "无法读取图片")), "图片处理失败：无法读取图片");
});

test("friendlyError AppError without detail uses label only", () => {
  assert.equal(friendlyError(new AppError("已取消")), "已取消");
  assert.equal(friendlyError(new AppError("图片处理失败", "")), "图片处理失败");
});

test("friendlyError AbortError maps to cancelled", () => {
  const e = new Error("The user aborted a request");
  e.name = "AbortError";
  assert.equal(friendlyError(e), "已取消");
});

test("friendlyError message containing 已取消 maps to cancelled", () => {
  assert.equal(friendlyError(new Error("任务已取消")), "已取消");
});

test("friendlyError unknown", () => {
  assert.match(friendlyError(new Error("boom")), /未知错误/);
});
