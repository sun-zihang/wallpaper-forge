// web/tests/cdn.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  JSZIP_URLS,
  GIFUCT_URLS,
  FFMPEG_URLS,
  FFMPEG_WORKER_URLS,
  FFMPEG_UTIL_URLS,
  FFMPEG_CORE_JS_URLS,
  FFMPEG_CORE_WASM_URLS,
  jsDelivr,
  unpkg,
  loadScriptFirst,
  importFirst,
  toBlobUrlFirst,
} from "../lib/cdn.js";

test("every dependency has at least two pinned mirrors", () => {
  const lists = {
    JSZIP_URLS,
    GIFUCT_URLS,
    FFMPEG_URLS,
    FFMPEG_WORKER_URLS,
    FFMPEG_UTIL_URLS,
    FFMPEG_CORE_JS_URLS,
    FFMPEG_CORE_WASM_URLS,
  };
  for (const [name, list] of Object.entries(lists)) {
    assert.ok(list.length >= 2, `${name} needs a fallback`);
    assert.equal(new Set(list).size, list.length, `${name} has duplicate mirrors`);
    for (const url of list) assert.match(url, /^https:\/\//, `${name} must be https`);
  }
});

test("mirrors keep the exact same pinned version as the primary", () => {
  assert.equal(jsDelivr("jszip@3.10.1/dist/jszip.min.js"), JSZIP_URLS[0]);
  assert.equal(unpkg("jszip@3.10.1/dist/jszip.min.js"), JSZIP_URLS[1]);
  assert.ok(FFMPEG_CORE_WASM_URLS.every((u) => u.includes("@ffmpeg/core@0.12.6")));
  assert.ok(GIFUCT_URLS.every((u) => u.includes("gifuct-js@2.1.2")));
});

test("loadScriptFirst falls through to the next mirror on error", async () => {
  const attempted = [];
  const loaded = await loadScriptFirst(["https://a/x.js", "https://b/x.js"], {
    createElement() {
      const el = { onload: null, onerror: null };
      let v = "";
      Object.defineProperty(el, "src", {
        set(value) {
          v = value;
          attempted.push(value);
          queueMicrotask(() => (v.includes("/a/") ? el.onerror() : el.onload()));
        },
      });
      return el;
    },
    append() {},
  });
  assert.equal(loaded, "https://b/x.js");
  assert.deepEqual(attempted, ["https://a/x.js", "https://b/x.js"]);
});

test("loadScriptFirst throws only after every mirror failed", async () => {
  await assert.rejects(
    () =>
      loadScriptFirst(["https://a/x.js", "https://b/x.js"], {
        createElement() {
          const el = { onload: null, onerror: null };
          Object.defineProperty(el, "src", {
            set() {
              queueMicrotask(() => el.onerror());
            },
          });
          return el;
        },
        append() {},
      }),
    /all mirrors failed/
  );
});

test("toBlobUrlFirst returns the first mirror that converts", async () => {
  const tried = [];
  const url = await toBlobUrlFirst(
    ["https://a/core.wasm", "https://b/core.wasm"],
    "application/wasm",
    async (u) => {
      tried.push(u);
      if (u.includes("/a/")) throw new Error("blocked");
      return `blob:${u}`;
    }
  );
  assert.equal(url, "blob:https://b/core.wasm");
  assert.deepEqual(tried, ["https://a/core.wasm", "https://b/core.wasm"]);
});

test("toBlobUrlFirst reports failure when all mirrors throw", async () => {
  await assert.rejects(
    () =>
      toBlobUrlFirst(["https://a/x", "https://b/x"], "text/javascript", async () => {
        throw new Error("nope");
      }),
    /all mirrors failed/
  );
});

test("importFirst skips a broken specifier and uses the next", async () => {
  const mod = await importFirst([
    "data:text/javascript,throw new Error('x')",
    "data:text/javascript,export const ok=1",
  ]);
  assert.equal(mod.ok, 1);
});
