// web/tests/onboarding.test.mjs
import test from "node:test";
import assert from "node:assert/strict";

function installDom() {
  const store = new Map();
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
  };
  const appended = [];
  globalThis.document = {
    createElement: () => ({
      className: "",
      innerHTML: "",
      attrs: {},
      listeners: new Map(),
      classList: {},
      setAttribute(k, v) {
        this.attrs[k] = v;
      },
      addEventListener() {},
      querySelector() {
        return { addEventListener() {} };
      },
      remove() {},
    }),
    body: {
      appendChild(el) {
        appended.push(el);
      },
    },
  };
  return { store, appended };
}

test("maybeShowOnboarding shows the tour on first visit", async () => {
  const { appended } = installDom();
  const { maybeShowOnboarding } = await import("../lib/onboarding.js");
  maybeShowOnboarding();
  assert.equal(appended.length, 1, "tour overlay appended");
  assert.equal(appended[0].className, "onboarding");
  assert.equal(appended[0].attrs["aria-label"], "新手引导");
});

test("maybeShowOnboarding does nothing once onboarded", async () => {
  const { store, appended } = installDom();
  store.set("wc.onboarded", "1");
  const { maybeShowOnboarding } = await import("../lib/onboarding.js");
  maybeShowOnboarding();
  assert.equal(appended.length, 0, "no tour after onboarding");
});

test("maybeShowOnboarding is a no-op without a document", async () => {
  const { maybeShowOnboarding } = await import("../lib/onboarding.js");
  const origDoc = globalThis.document;
  delete globalThis.document;
  try {
    maybeShowOnboarding();
  } finally {
    globalThis.document = origDoc;
  }
});
