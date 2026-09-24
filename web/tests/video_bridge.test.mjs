// web/tests/video_bridge.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { ensureFFmpeg, readFileToBlob, writeFileFromBlob } from "../lib/video_bridge.js";

function installFakes(captured) {
  globalThis.document = {
    createElement() {
      const el = { onload: null, onerror: null };
      Object.defineProperty(el, "src", {
        set(value) {
          captured.scripts.push(value);
          queueMicrotask(() => el.onload && el.onload());
        },
      });
      return el;
    },
    head: { appendChild() {} },
  };
  globalThis.FFmpegUtil = {
    async toBlobURL(url) {
      captured.blobUrls.push(url);
      return `blob:${url}`;
    },
  };
  globalThis.FFmpegWASM = {
    FFmpeg: class {
      async load(args) {
        captured.loadArgs = args;
      }
      async writeFile(path, data) {
        captured.written = { path, data };
      }
      async readFile(path) {
        return new Uint8Array([1, 2, 3, 4]);
      }
    },
  };
}

test("ensureFFmpeg passes a same-origin worker and an ESM core to load()", async () => {
  const captured = { scripts: [], blobUrls: [] };
  installFakes(captured);
  const inst = await ensureFFmpeg();

  assert.ok(inst, "returns an instance");
  assert.equal(captured.loadArgs.classWorkerURL.startsWith("blob:"), true);
  assert.match(
    captured.loadArgs.classWorkerURL,
    /@ffmpeg\/ffmpeg@0\.12\.10\/dist\/umd\/814\.ffmpeg\.js$/,
  );
  assert.match(captured.loadArgs.coreURL, /@ffmpeg\/core@0\.12\.6\/dist\/esm\/ffmpeg-core\.js$/);
  assert.match(captured.loadArgs.wasmURL, /@ffmpeg\/core@0\.12\.6\/dist\/esm\/ffmpeg-core\.wasm$/);
  assert.equal(captured.loadArgs.coreURL.startsWith("blob:"), true);
  assert.equal(captured.loadArgs.wasmURL.startsWith("blob:"), true);
  assert.equal(captured.loadArgs.coreURL.includes("dist/umd"), false);
  assert.equal(captured.loadArgs.wasmURL.includes("dist/umd"), false);
});

test("writeFileFromBlob writes raw bytes and readFileToBlob maps mime by extension", async () => {
  const written = {};
  const ff = {
    async writeFile(path, data) {
      written.path = path;
      written.data = data;
    },
    async readFile() {
      return new Uint8Array([1, 2, 3, 4]);
    },
  };

  await writeFileFromBlob(ff, "in.mp4", new Blob([new Uint8Array([9, 8, 7])]));
  assert.equal(written.path, "in.mp4");
  assert.deepEqual([...written.data], [9, 8, 7]);

  assert.equal((await readFileToBlob(ff, "a.gif")).type, "image/gif");
  assert.equal((await readFileToBlob(ff, "a.png")).type, "image/png");
  assert.equal((await readFileToBlob(ff, "a.webm")).type, "video/webm");
  assert.equal((await readFileToBlob(ff, "a.mp4")).type, "video/mp4");
  assert.deepEqual([...new Uint8Array(await (await readFileToBlob(ff, "a.mp4")).arrayBuffer())], [1, 2, 3, 4]);
});
