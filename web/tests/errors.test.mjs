import test from "node:test";
import assert from "node:assert/strict";
import { friendlyError, AppError } from "../lib/errors.js";

test("friendlyError maps AppError", () => {
  const out = friendlyError(new AppError("图片处理失败", "无法读取图片"));
  assert.match(out, /文件损坏或格式无法识别/);
  assert.match(out, /试试重新下载/);
});

test("friendlyError AppError without detail uses label only", () => {
  assert.equal(friendlyError(new AppError("已取消")), "已取消");
  assert.equal(friendlyError(new AppError("图片处理失败", "")), "图片处理失败");
});

test("friendlyError categorizes corrupt files", () => {
  const out = friendlyError(new Error("文件头无法识别为图片"));
  assert.match(out, /文件损坏或格式无法识别/);
});

test("friendlyError categorizes engine failures", () => {
  const out = friendlyError(new Error("视频引擎加载失败"));
  assert.match(out, /处理引擎加载失败/);
  assert.match(out, /Chrome/);
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

test("friendlyError handles null, undefined and plain strings", () => {
  assert.match(friendlyError(null), /未知错误/);
  assert.match(friendlyError(undefined), /未知错误/);
  assert.match(friendlyError("boom"), /未知错误/);
  assert.match(friendlyError(42), /42/);
});

test("friendlyError limit category keeps the specific detail", () => {
  const out = friendlyError(new AppError("视频添加失败", "单文件超过 100MB 上限，请改用桌面版"));
  assert.match(out, /超出 Web 端处理上限/);
  assert.match(out, /100MB/);
  const res = friendlyError(new AppError("图片添加失败", "图片分辨率使用过高：9000×9000，超出 Web 端处理上限"));
  assert.match(res, /9000/);
});
