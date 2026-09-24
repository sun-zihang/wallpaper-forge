import test from "node:test";
import assert from "node:assert/strict";
import { DEP_VERSIONS } from "../lib/deps.js";
import {
  JSZIP_URLS,
  GIFUCT_URLS,
  FFMPEG_URLS,
  FFMPEG_WORKER_URLS,
  FFMPEG_UTIL_URLS,
  FFMPEG_CORE_JS_URLS,
  FFMPEG_CORE_WASM_URLS,
} from "../lib/cdn.js";

test("DEP_VERSIONS lists every pinned runtime dep", () => {
  assert.deepEqual(Object.keys(DEP_VERSIONS).sort(), [
    "core",
    "ffmpeg",
    "ffmpeg-util",
    "gifuct",
    "jszip",
  ]);
});

test("DEP_VERSIONS matches the CDN pin for each package", () => {
  assert.ok(JSZIP_URLS.every((u) => u.includes(`jszip@${DEP_VERSIONS.jszip}`)));
  assert.ok(GIFUCT_URLS.every((u) => u.includes(`gifuct-js@${DEP_VERSIONS.gifuct}`)));
  assert.ok(
    FFMPEG_URLS.every((u) => u.includes(`@ffmpeg/ffmpeg@${DEP_VERSIONS.ffmpeg}`)),
  );
  assert.ok(
    FFMPEG_WORKER_URLS.every((u) =>
      u.includes(`@ffmpeg/ffmpeg@${DEP_VERSIONS.ffmpeg}`),
    ),
  );
  assert.ok(
    FFMPEG_UTIL_URLS.every((u) =>
      u.includes(`@ffmpeg/util@${DEP_VERSIONS["ffmpeg-util"]}`),
    ),
  );
  assert.ok(
    FFMPEG_CORE_JS_URLS.every((u) =>
      u.includes(`@ffmpeg/core@${DEP_VERSIONS.core}`),
    ),
  );
  assert.ok(
    FFMPEG_CORE_WASM_URLS.every((u) =>
      u.includes(`@ffmpeg/core@${DEP_VERSIONS.core}`),
    ),
  );
});
