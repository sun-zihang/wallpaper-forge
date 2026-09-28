// web/tests/onboarding.test.mjs
import test from "node:test";
import assert from "node:assert/strict";

function installDom() {
  const store = new Map();
  let failWrites = false;
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => {
      if (failWrites) throw new Error("quota");
      store.set(k, String(v));
    },
    removeItem: (k) => store.delete(k),
  };
  const appended = [];
  const makeEl = () => ({
    className: "",
    innerHTML: "",
    attrs: {},
    removed: false,
    _qs: new Map(),
    setAttribute(k, v) {
      this.attrs[k] = v;
    },
    addEventListener() {},
    querySelector(sel) {
      if (!this._qs.has(sel)) {
        const target = {
          listeners: {},
          addEventListener(type, fn) {
            this.listeners[type] = fn;
          },
        };
        this._qs.set(sel, target);
      }
      return this._qs.get(sel);
    },
    remove() {
      this.removed = true;
    },
  });
  globalThis.document = {
    createElement: () => makeEl(),
    body: {
      appendChild(el) {
        appended.push(el);
      },
    },
  };
  return { store, appended, setFailWrites: (v) => (failWrites = v) };
}

function fire(overlay, sel) {
  const fn = overlay.querySelector(sel).listeners.click;
  assert.equal(typeof fn, "function", `click listener bound for ${sel}`);
  fn();
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

test("next walks every step and finish marks onboarded", async () => {
  const { store, appended } = installDom();
  const { maybeShowOnboarding } = await import("../lib/onboarding.js");
  maybeShowOnboarding();
  const overlay = appended[0];
  assert.match(overlay.innerHTML, /1 \/ 4/);
  assert.match(overlay.innerHTML, /跳过引导/);
  fire(overlay, '[data-act="next"]');
  assert.match(overlay.innerHTML, /2 \/ 4/);
  fire(overlay, '[data-act="next"]');
  assert.match(overlay.innerHTML, /3 \/ 4/);
  fire(overlay, '[data-act="next"]');
  assert.match(overlay.innerHTML, /4 \/ 4/);
  assert.match(overlay.innerHTML, /完成/);
  fire(overlay, '[data-act="next"]');
  assert.equal(store.get("wc.onboarded"), "1", "flag persisted on finish");
  assert.equal(overlay.removed, true, "overlay removed");
});

test("skip exits immediately, persists flag, and later clicks are safe", async () => {
  const { store, appended } = installDom();
  const { maybeShowOnboarding } = await import("../lib/onboarding.js");
  maybeShowOnboarding();
  const overlay = appended[0];
  fire(overlay, '[data-act="skip"]');
  assert.equal(store.get("wc.onboarded"), "1", "flag persisted on skip");
  assert.equal(overlay.removed, true, "overlay removed on skip");
  fire(overlay, '[data-act="next"]');
  assert.equal(store.get("wc.onboarded"), "1", "still persisted after stray click");
  assert.equal(overlay.removed, true, "no double-removal crash");
});

test("finish survives localStorage write failures", async () => {
  const { appended, setFailWrites } = installDom();
  setFailWrites(true);
  const { maybeShowOnboarding } = await import("../lib/onboarding.js");
  maybeShowOnboarding();
  const overlay = appended[0];
  fire(overlay, '[data-act="skip"]');
  assert.equal(overlay.removed, true, "overlay removed even when write throws");
});
