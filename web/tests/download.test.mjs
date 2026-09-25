// web/tests/download.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { baseName, stem, downloadBlob } from "../lib/download.js";

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
