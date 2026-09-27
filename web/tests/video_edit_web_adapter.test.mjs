import test from "node:test";
import assert from "node:assert/strict";
import { WebAdapter } from "../lib/video_edit/web/adapter.js";

function makeMockFFmpeg() {
  const files = new Map();
  return {
    files,
    execCalls: [],
    async exec(args) {
      this.execCalls.push(args);
      return 0;
    },
    async writeFile(path, data) {
      files.set(path, data);
    },
    async readFile(path) {
      return files.get(path);
    },
    async deleteFile(path) {
      files.delete(path);
    },
    async listDir() {
      return [...files.keys()];
    },
  };
}

test("WebAdapter: writeFile 存储 Blob 到虚拟 FS", async () => {
  const ff = makeMockFFmpeg();
  const adapter = new WebAdapter(ff);
  await adapter.writeFile("test.txt", new Blob(["hello"]));
  assert.ok(ff.files.has("test.txt"));
});

test("WebAdapter: readFile 返回 Blob", async () => {
  const ff = makeMockFFmpeg();
  const adapter = new WebAdapter(ff);
  await adapter.writeFile("test.txt", new Blob(["hello"]));
  const blob = await adapter.readFile("test.txt");
  assert.ok(blob instanceof Blob);
});

test("WebAdapter: deleteFile 删除文件", async () => {
  const ff = makeMockFFmpeg();
  const adapter = new WebAdapter(ff);
  await adapter.writeFile("test.txt", new Blob(["hello"]));
  await adapter.deleteFile("test.txt");
  assert.equal(ff.files.has("test.txt"), false);
});

test("WebAdapter: runFFmpeg 调用 ff.exec", async () => {
  const ff = makeMockFFmpeg();
  const adapter = new WebAdapter(ff);
  await adapter.runFFmpeg(["-i", "in.mp4", "out.mp4"], "out.mp4", () => {});
  assert.equal(ff.execCalls.length, 1);
  assert.deepEqual(ff.execCalls[0], ["-i", "in.mp4", "out.mp4"]);
});
