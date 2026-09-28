// web/tests/i18n.test.mjs
import test from "node:test";
import assert from "node:assert/strict";

function installStorage() {
  const store = new Map();
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
  };
  return store;
}

test("getLang defaults to zh for empty or invalid values", async () => {
  const store = installStorage();
  const { getLang } = await import("../lib/i18n.js");
  assert.equal(getLang(), "zh");
  store.set("wc.lang", "fr");
  assert.equal(getLang(), "zh");
  store.set("wc.lang", "zh");
  assert.equal(getLang(), "zh");
});

test("setLang persists en and normalizes invalid input", async () => {
  const store = installStorage();
  const { getLang, setLang } = await import("../lib/i18n.js");
  assert.equal(setLang("en"), "en");
  assert.equal(store.get("wc.lang"), "en");
  assert.equal(getLang(), "en");
  assert.equal(setLang("xx"), "zh");
  assert.equal(store.get("wc.lang"), "zh");
});

test("i18n survives a throwing localStorage", async () => {
  globalThis.localStorage = {
    getItem() {
      throw new Error("blocked");
    },
    setItem() {
      throw new Error("blocked");
    },
  };
  const { getLang, setLang } = await import("../lib/i18n.js");
  assert.equal(getLang(), "zh");
  assert.equal(setLang("en"), "en");
});
