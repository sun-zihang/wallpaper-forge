// web/tests/download.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  baseName,
  stem,
  downloadBlob,
  supportsFileSystemAccess,
  pickOutputDirectory,
  writeBlobToDirectory,
  saveBlobsToDirectory,
  enableDragSave,
} from "../lib/download.js";

test("path helpers normalise windows separators", () => {
  assert.equal(baseName("C:\\a\\b\\c.png"), "c.png");
  assert.equal(stem("C:\\a\\b\\c.png"), "c");
  assert.equal(stem("noext"), "noext");
  assert.equal(stem(".hidden"), ".hidden");
});

test("stem keeps only the final extension", () => {
  assert.equal(stem("archive.tar.gz"), "archive.tar");
  assert.equal(stem("a.b.c"), "a.b");
  assert.equal(stem("trailing."), "trailing");
  assert.equal(baseName("/only/one/"), "");
});

test("path helpers tolerate empty and non-string input", () => {
  assert.equal(baseName(""), "");
  assert.equal(stem(""), "");
  assert.equal(stem("..."), "..");
  assert.equal(baseName(null), "null");
});

test("downloadBlob clicks a temporary anchor and revokes the object URL", () => {
  const created = [];
  const appended = [];
  const removed = [];
  const timeouts = [];
  const revoked = [];
  const origCreateEl = globalThis.document?.createElement;
  const origBody = globalThis.document?.body;
  const origCreate = URL.createObjectURL;
  const origRevoke = URL.revokeObjectURL;
  const origSetTimeout = globalThis.setTimeout;

  globalThis.document = {
    createElement(tag) {
      const el = {
        tagName: tag,
        href: "",
        download: "",
        clicked: false,
        click() {
          el.clicked = true;
        },
        remove() {
          removed.push(el);
        },
      };
      created.push(el);
      return el;
    },
    body: {
      appendChild(el) {
        appended.push(el);
      },
    },
  };
  URL.createObjectURL = () => "blob:dl";
  URL.revokeObjectURL = (u) => revoked.push(u);
  globalThis.setTimeout = (fn, ms) => {
    timeouts.push(ms);
    fn();
    return 1;
  };

  try {
    downloadBlob(new Blob(["payload"]), "out.png");
  } finally {
    if (origCreateEl) {
      globalThis.document.createElement = origCreateEl;
      globalThis.document.body = origBody;
    } else {
      delete globalThis.document;
    }
    URL.createObjectURL = origCreate;
    URL.revokeObjectURL = origRevoke;
    globalThis.setTimeout = origSetTimeout;
  }

  assert.equal(created.length, 1);
  const el = created[0];
  assert.equal(el.tagName, "a");
  assert.equal(el.href, "blob:dl");
  assert.equal(el.download, "out.png");
  assert.equal(el.clicked, true);
  assert.deepEqual(appended, [el]);
  assert.deepEqual(removed, [el]);
  assert.deepEqual(timeouts, [30_000]);
  assert.deepEqual(revoked, ["blob:dl"]);
});

test("supportsFileSystemAccess reflects showDirectoryPicker availability", () => {
  const origWindow = globalThis.window;
  try {
    delete globalThis.window;
    assert.equal(supportsFileSystemAccess(), false);
    globalThis.window = {};
    assert.equal(supportsFileSystemAccess(), false);
    globalThis.window = { showDirectoryPicker: () => Promise.resolve({}) };
    assert.equal(supportsFileSystemAccess(), true);
  } finally {
    if (origWindow === undefined) delete globalThis.window;
    else globalThis.window = origWindow;
  }
});

test("pickOutputDirectory wraps picker errors as AppError", async () => {
  const origWindow = globalThis.window;
  try {
    globalThis.window = {
      showDirectoryPicker: async () => {
        const e = new Error("nope");
        e.name = "AbortError";
        throw e;
      },
    };
    await assert.rejects(() => pickOutputDirectory(), (err) => {
      assert.equal(err.label, "保存失败");
      assert.equal(err.detail, "已取消选择");
      return true;
    });
    globalThis.window = {
      showDirectoryPicker: async () => {
        throw new Error("denied");
      },
    };
    await assert.rejects(() => pickOutputDirectory(), /无法打开文件夹选择器: denied/);
    globalThis.window = {};
    await assert.rejects(() => pickOutputDirectory(), /不支持直接保存到文件夹/);
  } finally {
    if (origWindow === undefined) delete globalThis.window;
    else globalThis.window = origWindow;
  }
});

test("writeBlobToDirectory and saveBlobsToDirectory write via the handle API", async () => {
  const closed = [];
  const written = [];
  const makeHandle = (name) => ({
    getFileHandle: async (fname, opts) => {
      assert.equal(fname, name);
      assert.deepEqual(opts, { create: true });
      return {
        createWritable: async () => ({
          write: async (blob) => written.push([name, blob]),
          close: async () => closed.push(name),
        }),
      };
    },
  });
  const dir = makeHandle("a.png");
  assert.equal(await writeBlobToDirectory(dir, new Blob(["x"]), "a.png"), "a.png");
  assert.deepEqual(closed, ["a.png"]);

  const dir2 = {
    getFileHandle: async (fname) => makeHandle(fname).getFileHandle(fname),
  };
  const written2 = [];
  const origClosed = closed.length;
  // route through a fresh handle factory so each name gets its own writable
  const dir3 = {
    getFileHandle: async (fname) => ({
      createWritable: async () => ({
        write: async (blob) => written2.push([fname, blob]),
        close: async () => closed.push(fname),
      }),
    }),
  };
  const names = await saveBlobsToDirectory(dir3, [
    { blob: new Blob(["1"]), filename: "1.png" },
    { blob: new Blob(["2"]), filename: "2.png" },
  ]);
  assert.deepEqual(names, ["1.png", "2.png"]);
  assert.deepEqual(written2.map((w) => w[0]), ["1.png", "2.png"], "written sequentially");
  assert.equal(closed.length, origClosed + 2, "every writable is closed");
});

test("enableDragSave marks the element and packs a File into dragstart", () => {
  const attrs = {};
  const listeners = new Map();
  const el = {
    setAttribute(k, v) {
      attrs[k] = v;
    },
    addEventListener(type, fn) {
      listeners.set(type, fn);
    },
  };
  const added = [];
  const ev = {
    dataTransfer: {
      items: { add: (f) => added.push(f) },
      effectAllowed: "",
    },
  };
  assert.equal(enableDragSave(el, new Blob(["x"], { type: "image/png" }), "out.png"), true);
  assert.equal(attrs.draggable, "true");
  listeners.get("dragstart")(ev);
  assert.equal(added.length, 1);
  assert.equal(added[0].name, "out.png");
  assert.equal(added[0].type, "image/png");
  assert.equal(ev.dataTransfer.effectAllowed, "copy");
});

test("enableDragSave tolerates elements without setAttribute and dt without items", () => {
  assert.equal(enableDragSave(null, new Blob(["x"]), "a.png"), false);
  assert.equal(enableDragSave({}, new Blob(["x"]), "a.png"), false);
  const listeners = new Map();
  const el = {
    setAttribute() {},
    addEventListener(type, fn) {
      listeners.set(type, fn);
    },
  };
  enableDragSave(el, new Blob(["x"]), "a.png");
  listeners.get("dragstart")({ dataTransfer: {} });
  listeners.get("dragstart")({});
});
