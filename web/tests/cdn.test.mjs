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
  SCRIPT_INTEGRITY,
  jsDelivr,
  unpkg,
  loadScriptFirst,
  loadScriptFirstOnce,
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

test("loadScriptFirstOnce shares one in-flight load between concurrent callers", async () => {
  let created = 0;
  const create = () => {
    created += 1;
    const el = { onload: null, onerror: null };
    Object.defineProperty(el, "src", {
      set() {
        queueMicrotask(() => el.onload());
      },
    });
    return el;
  };
  const opts = { createElement: create, append() {} };
  const urls = ["https://once-cache/x.js"];
  const [a, b] = [loadScriptFirstOnce(urls, opts), loadScriptFirstOnce(urls, opts)];
  assert.equal(a, b, "same promise for the same URL list");
  assert.equal(await a, "https://once-cache/x.js");
  assert.equal(created, 1, "script injected exactly once");
  // a completed load is also reused by later callers
  assert.equal(await loadScriptFirstOnce(urls, opts), "https://once-cache/x.js");
  assert.equal(created, 1);
});

test("loadScriptFirstOnce does not cache failures and retries fresh", async () => {
  let fail = true;
  const create = () => {
    const el = { onload: null, onerror: null };
    Object.defineProperty(el, "src", {
      set() {
        queueMicrotask(() => (fail ? el.onerror() : el.onload()));
      },
    });
    return el;
  };
  const opts = { createElement: create, append() {} };
  const urls = ["https://once-retry/x.js"];
  await assert.rejects(() => loadScriptFirstOnce(urls, opts), /all mirrors failed/);
  fail = false;
  assert.equal(await loadScriptFirstOnce(urls, opts), "https://once-retry/x.js");
});

test("SCRIPT_INTEGRITY covers exactly the script-tag deps, both mirrors, valid format", () => {
  const pinned = [
    ...JSZIP_URLS,
    ...FFMPEG_URLS,
    ...FFMPEG_WORKER_URLS,
    ...FFMPEG_UTIL_URLS,
  ];
  assert.equal(Object.keys(SCRIPT_INTEGRITY).length, pinned.length, "one SRI pin per script URL");
  assert.deepEqual(
    [...Object.keys(SCRIPT_INTEGRITY)].sort(),
    [...pinned].sort(),
    "SRI pins must match the script-tag URL set exactly (no stale, no missing)",
  );
  for (const [url, integrity] of Object.entries(SCRIPT_INTEGRITY)) {
    assert.match(integrity, /^sha384-[A-Za-z0-9+/]+={0,2}$/, `bad integrity for ${url}`);
  }
  // jsDelivr 与 unpkg 镜像必须共享同一哈希（同一 npm dist 文件字节一致的前提由
  // scripts/check_cdn.mjs 每次推送在线验证）
  for (const [primary, twin] of [
    [JSZIP_URLS[0], JSZIP_URLS[1]],
    [FFMPEG_URLS[0], FFMPEG_URLS[1]],
    [FFMPEG_WORKER_URLS[0], FFMPEG_WORKER_URLS[1]],
    [FFMPEG_UTIL_URLS[0], FFMPEG_UTIL_URLS[1]],
  ]) {
    assert.equal(SCRIPT_INTEGRITY[primary], SCRIPT_INTEGRITY[twin], `mirror hash drift: ${primary}`);
  }
  // ESM deps loaded via import() have no integrity channel — must stay unpinned
  for (const url of [...GIFUCT_URLS, ...FFMPEG_CORE_JS_URLS, ...FFMPEG_CORE_WASM_URLS]) {
    assert.equal(SCRIPT_INTEGRITY[url], undefined, `unexpected SRI pin for import()-loaded ${url}`);
  }
});

test("loadScriptFirst attaches integrity + crossOrigin for pinned URLs", async () => {
  const url = JSZIP_URLS[0];
  const created = [];
  const loaded = await loadScriptFirst([url], {
    createElement() {
      const el = { onload: null, onerror: null };
      Object.defineProperty(el, "src", {
        set() {
          queueMicrotask(() => el.onload());
        },
      });
      created.push(el);
      return el;
    },
    append() {},
  });
  assert.equal(loaded, url);
  assert.equal(created[0].integrity, SCRIPT_INTEGRITY[url]);
  assert.equal(created[0].crossOrigin, "anonymous");
});

test("loadScriptFirst leaves unpinned URLs untouched", async () => {
  const created = [];
  const loaded = await loadScriptFirst(["https://unpinned.example/x.js"], {
    createElement() {
      const el = { onload: null, onerror: null };
      Object.defineProperty(el, "src", {
        set() {
          queueMicrotask(() => el.onload());
        },
      });
      created.push(el);
      return el;
    },
    append() {},
  });
  assert.equal(created[0].integrity, undefined);
  assert.equal(created[0].crossOrigin, undefined);
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
