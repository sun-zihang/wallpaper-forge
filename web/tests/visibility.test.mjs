// web/tests/visibility.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { isDocumentHidden, onVisibilityChange } from "../lib/visibility.js";

test("isDocumentHidden is false without a document", () => {
  assert.equal(isDocumentHidden(), false);
});

test("onVisibilityChange is a no-op without a document", () => {
  const off = onVisibilityChange(() => assert.fail("must not fire"));
  off();
});

test("onVisibilityChange fires on hidden and visible transitions", () => {
  const origDoc = globalThis.document;
  const listeners = new Map();
  let hidden = false;
  globalThis.document = {
    get hidden() {
      return hidden;
    },
    addEventListener(type, fn) {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(fn);
    },
    removeEventListener(type, fn) {
      const list = listeners.get(type) || [];
      const i = list.indexOf(fn);
      if (i >= 0) list.splice(i, 1);
    },
  };
  try {
    const events = [];
    const off = onVisibilityChange((h) => events.push(h));
    assert.equal(isDocumentHidden(), false);
    const fire = () => {
      for (const fn of listeners.get("visibilitychange") || []) fn();
    };
    hidden = true;
    fire();
    assert.equal(isDocumentHidden(), true);
    hidden = false;
    fire();
    assert.deepEqual(events, [true, false]);
    off();
    hidden = true;
    fire();
    assert.deepEqual(events, [true, false], "unsubscribed listener must not fire");
  } finally {
    globalThis.document = origDoc;
  }
});
