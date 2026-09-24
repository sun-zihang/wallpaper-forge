// web/tests/drop.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { filterDropped } from "../lib/drop.js";

const f = (name) => ({ name, size: 10 });

test("keeps everything when no extension filter is given", () => {
  const files = [f("a.bin"), f("b.txt")];
  const { kept, rejected } = filterDropped(files);
  assert.deepEqual(kept.map((x) => x.name), ["a.bin", "b.txt"]);
  assert.deepEqual(rejected, []);
});

test("splits keep/reject on extension, case-insensitively", () => {
  const { kept, rejected } = filterDropped(
    [f("a.PKG"), f("b.tex"), f("c.mp4"), f("d")],
    [".pkg", ".tex", ".mpkg"]
  );
  assert.deepEqual(kept.map((x) => x.name), ["a.PKG", "b.tex"]);
  assert.deepEqual(rejected.map((x) => x.name), ["c.mp4", "d"]);
});

test("handles empty and missing input", () => {
  assert.deepEqual(filterDropped([], [".png"]), { kept: [], rejected: [] });
  assert.deepEqual(filterDropped(null, [".png"]), { kept: [], rejected: [] });
});

test("attachments extension without leading dot still matches", () => {
  const { kept, rejected } = filterDropped(
    [f("a.png"), f("b.gif")],
    ["png"],
  );
  assert.deepEqual(kept.map((x) => x.name), ["a.png"]);
  assert.deepEqual(rejected.map((x) => x.name), ["b.gif"]);
});

// Minimal DOM fakes so attachDropTarget/bindDocumentDrop can run under node:test.
function makeDom() {
  const listeners = new Map();
  const doc = {
    addEventListener(type, fn) {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(fn);
    },
    _fire(type, ev) {
      for (const fn of listeners.get(type) || []) fn(ev);
    },
    _listeners: listeners,
  };
  const el = {
    classList: {
      _set: new Set(),
      add(c) {
        this._set.add(c);
      },
      remove(c) {
        this._set.delete(c);
      },
      contains(c) {
        return this._set.has(c);
      },
    },
    _listeners: new Map(),
    addEventListener(type, fn) {
      if (!this._listeners.has(type)) this._listeners.set(type, []);
      this._listeners.get(type).push(fn);
    },
    _fire(type, ev) {
      for (const fn of this._listeners.get(type) || []) fn(ev);
    },
  };
  return { doc, el };
}

function fakeDataTransfer(files) {
  const store = [...files];
  const items = {
    _list: store,
    add(f) {
      store.push(f);
    },
  };
  // assign is a plain array-like with length; drop.js spreads it
  const filesProxy = Object.assign([], store);
  return {
    get files() {
      filesProxy.length = 0;
      for (const f of store) filesProxy.push(f);
      return filesProxy;
    },
    types: ["Files"],
    items,
  };
}

// Node has no DataTransfer/Event constructor used by drop.js
if (typeof globalThis.DataTransfer === "undefined") {
  globalThis.DataTransfer = class DataTransfer {
    constructor() {
      this._files = [];
      this.items = {
        add: (f) => this._files.push(f),
      };
    }
    get files() {
      const arr = Object.assign([], this._files);
      return arr;
    }
  };
}
if (typeof globalThis.Event === "undefined") {
  globalThis.Event = class Event {
    constructor(type, init = {}) {
      this.type = type;
      this.bubbles = !!init.bubbles;
    }
  };
}

test("attachDropTarget filters, reports rejected, and merges into input", async () => {
  const { bindDocumentDrop, attachDropTarget } = await import("../lib/drop.js");
  const { doc, el } = makeDom();
  globalThis.document = doc;

  const rejectedMsgs = [];
  const input = {
    files: Object.assign([], {}),
    _events: [],
    dispatchEvent(ev) {
      this._events.push(ev.type);
    },
  };
  // seed with one existing file
  const existing = f("old.png");
  input.files = Object.assign([existing], {});

  bindDocumentDrop();
  attachDropTarget(el, input, {
    extensions: [".png", ".jpg"],
    onRejected: (m) => rejectedMsgs.push(m),
  });

  const dt = fakeDataTransfer([f("keep.png"), f("skip.gif")]);
  let prevented = 0;
  el._fire("drop", {
    preventDefault() {
      prevented += 1;
    },
    dataTransfer: dt,
  });
  assert.equal(prevented, 1);
  assert.ok(rejectedMsgs.length === 1 && rejectedMsgs[0].includes("skip.gif"));
  assert.equal(input.files.length, 2);
  assert.deepEqual(
    [...input.files].map((x) => x.name),
    ["old.png", "keep.png"],
  );
  assert.ok(input._events.includes("change"));
  assert.ok(!el.classList.contains("hot"));

  // dragover adds .hot; dragleave removes it
  el._fire("dragover", { preventDefault() {} });
  assert.ok(el.classList.contains("hot"));
  el._fire("dragleave", {});
  assert.ok(!el.classList.contains("hot"));

  // document drop without active target is a no-op; with active forwards
  let docPrevented = 0;
  doc._fire("dragover", {
    preventDefault() {
      docPrevented += 1;
    },
    dataTransfer: { types: ["Files"] },
  });
  assert.ok(docPrevented >= 1);

  const before = input.files.length;
  doc._fire("drop", {
    preventDefault() {},
    dataTransfer: fakeDataTransfer([f("doc.png")]),
  });
  // activeTarget still attached → merges
  assert.equal(input.files.length, before + 1);

  // null input on a fresh target: apply reports rejected but cannot merge
  const { el: el2 } = makeDom();
  attachDropTarget(el2, null, {
    extensions: [".png"],
    onRejected: (m) => rejectedMsgs.push(m),
  });
  const msgsBefore = rejectedMsgs.length;
  el2._fire("drop", {
    preventDefault() {},
    dataTransfer: fakeDataTransfer([f("x.gif")]),
  });
  assert.equal(rejectedMsgs.length, msgsBefore + 1);
  assert.ok(rejectedMsgs.at(-1).includes("x.gif"));
});

test("bindDocumentDrop dragover ignores non-File drags", async () => {
  const { bindDocumentDrop, attachDropTarget } = await import("../lib/drop.js");
  const { doc, el } = makeDom();
  globalThis.document = doc;
  bindDocumentDrop();
  attachDropTarget(el, null, { extensions: null });

  let prevented = 0;
  doc._fire("dragover", {
    preventDefault() {
      prevented += 1;
    },
    dataTransfer: { types: ["text/plain"] },
  });
  assert.equal(prevented, 0);

  doc._fire("dragover", {
    preventDefault() {
      prevented += 1;
    },
    dataTransfer: { types: ["Files"] },
  });
  assert.equal(prevented, 1);
});
