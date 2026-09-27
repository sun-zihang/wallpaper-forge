// web/tests/settings.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { DEFAULT_SETTINGS, loadSettings, saveSettings, applyTheme } from "../lib/settings.js";

function installStorage() {
  const store = new Map();
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
  };
  return store;
}

function installBody() {
  const classes = new Set();
  globalThis.document = {
    body: {
      classList: {
        toggle(c, on) {
          if (on) classes.add(c);
          else classes.delete(c);
        },
        contains: (c) => classes.has(c),
      },
    },
  };
  return classes;
}

test("loadSettings returns defaults with no stored value", () => {
  installStorage();
  assert.deepEqual(loadSettings(), DEFAULT_SETTINGS);
});

test("saveSettings merges and persists", () => {
  const store = installStorage();
  saveSettings({ theme: "light", videoCrf: 28 });
  const s = loadSettings();
  assert.equal(s.theme, "light");
  assert.equal(s.videoCrf, 28);
  assert.equal(s.imageFormat, "JPG", "untouched keys keep defaults");
  assert.equal(store.has("wc.settings"), true);
});

test("loadSettings tolerates corrupt storage", () => {
  const store = installStorage();
  store.set("wc.settings", "{not json");
  const s = loadSettings();
  assert.equal(s.theme, "dark", "falls back to defaults");
});

test("applyTheme toggles the light class on body", () => {
  installStorage();
  const classes = installBody();
  globalThis.window = { matchMedia: () => ({ matches: false }) };
  applyTheme("light");
  assert.equal(classes.has("light"), true);
  applyTheme("dark");
  assert.equal(classes.has("light"), false);
});

test("applyTheme system follows prefers-color-scheme", () => {
  installStorage();
  const classes = installBody();
  globalThis.window = { matchMedia: () => ({ matches: true }) };
  applyTheme("system");
  assert.equal(classes.has("light"), true, "system + light preference -> light");
  globalThis.window = { matchMedia: () => ({ matches: false }) };
  applyTheme("system");
  assert.equal(classes.has("light"), false, "system + dark preference -> dark");
});
