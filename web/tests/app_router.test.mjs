// web/tests/app_router.test.mjs
// Router behavior for app.js: home render, unknown-hash fallback, nav
// highlighting, and the status bar. Lazy page mounts need a real DOM, so they
// stay covered by the smoke script rather than these stubs.
import test from "node:test";
import assert from "node:assert/strict";

function anchor(href) {
  const classes = new Set();
  return {
    getAttribute: (name) => (name === "href" ? href : null),
    classList: {
      toggle(name, on) {
        if (on) classes.add(name);
        else classes.delete(name);
      },
      contains: (name) => classes.has(name),
    },
  };
}

function installAppDom() {
  const root = { innerHTML: "" };
  const status = { textContent: "就绪" };
  const navAnchors = [anchor("#/"), anchor("#/image"), anchor("#/gif")];
  const hashChange = [];
  globalThis.document = {
    getElementById: (id) => {
      if (id === "app") return root;
      if (id === "status") return status;
      return null; // footer is absent → renderFooter exits early
    },
    querySelectorAll: (sel) => (sel === ".rail nav a" ? navAnchors : []),
    addEventListener() {},
    createElement: (tag) => ({ tag, style: {}, appendChild() {} }),
  };
  globalThis.window = {
    addEventListener: (type, fn) => {
      if (type === "hashchange") hashChange.push(fn);
    },
  };
  // emulate the browser: assigning location.hash fires hashchange asynchronously
  let currentHash = "#/";
  const loc = {};
  Object.defineProperty(loc, "hash", {
    get: () => currentHash,
    set(v) {
      if (v === currentHash) return;
      currentHash = v;
      queueMicrotask(() => hashChange.forEach((fn) => fn()));
    },
  });
  globalThis.location = loc;
  return { root, status, navAnchors, hashChange, location: loc };
}

const dom = installAppDom();
const { setStatus } = await import("../app.js");
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

test("initial render mounts home and setStatus drives the status bar", async () => {
  await flush();
  assert.ok(dom.root.innerHTML.includes("在浏览器里处理壁纸"), "home rendered");
  assert.ok(dom.root.innerHTML.includes("#/unpack"), "home links every section");
  assert.ok(dom.hashChange.length === 1, "one hashchange listener registered");

  setStatus("测试状态");
  assert.equal(dom.status.textContent, "测试状态");

  // the home link is active while the lazy links are not
  assert.equal(dom.navAnchors[0].classList.contains("active"), true);
  assert.equal(dom.navAnchors[1].classList.contains("active"), false);
});

test("unknown hash falls back to home and re-renders", async () => {
  globalThis.location.hash = "#/nope";
  await flush();
  await flush();
  assert.equal(dom.location.hash, "#/", "redirected home");
  assert.ok(dom.root.innerHTML.includes("在浏览器里处理壁纸"), "home rendered after fallback");
  assert.equal(dom.navAnchors[0].classList.contains("active"), true);
  assert.equal(dom.navAnchors[1].classList.contains("active"), false);
});
