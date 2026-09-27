// web/tests/errors-ui.test.mjs
import test from "node:test";
import assert from "node:assert/strict";

function makeEl() {
  const el = {
    tagName: "div",
    className: "",
    innerHTML: "",
    textContent: "",
    attrs: {},
    children: {},
    listeners: new Map(),
    classList: {},
    setAttribute(k, v) {
      this.attrs[k] = v;
    },
    addEventListener(type, fn) {
      if (!this.listeners.has(type)) this.listeners.set(type, []);
      this.listeners.get(type).push(fn);
    },
    querySelector(sel) {
      if (!el.children[sel]) el.children[sel] = makeEl();
      return el.children[sel];
    },
    appendChild(c) {
      el.children[c.className || Object.keys(el.children).length] = c;
    },
    remove() {
      el.removed = true;
    },
  };
  return el;
}

function installDom() {
  const appended = [];
  globalThis.document = {
    createElement: () => makeEl(),
    body: {
      appendChild(el) {
        appended.push(el);
      },
      prepend(el) {
        appended.unshift(el);
      },
    },
  };
  return appended;
}

test("showErrorModal renders title, body and actions", async () => {
  const appended = installDom();
  const { showErrorModal } = await import("../lib/errors-ui.js");
  const clicks = [];
  showErrorModal({
    title: "出错了",
    body: "<p>详情</p>",
    actions: [
      { label: "重试", primary: true, onClick: () => clicks.push("retry") },
      { label: "取消" },
    ],
  });
  const modal = appended[0];
  assert.ok(modal.className.includes("error-modal"));
  assert.equal(modal.children["h2"].textContent, "出错了");
  assert.equal(modal.children[".error-modal-body"].innerHTML, "<p>详情</p>");
  const actions = modal.children[".error-modal-actions"];
  const labels = Object.values(actions.children).map((b) => b.textContent);
  assert.deepEqual(labels, ["重试", "取消"]);
});

test("missingRequiredApis returns an array", async () => {
  const { missingRequiredApis } = await import("../lib/errors-ui.js");
  assert.ok(Array.isArray(missingRequiredApis()));
});

test("installCompatBanner is a no-op without document", async () => {
  const { installCompatBanner } = await import("../lib/errors-ui.js");
  const orig = globalThis.document;
  delete globalThis.document;
  try {
    installCompatBanner();
  } finally {
    globalThis.document = orig;
  }
});

test("error modal action button fires onClick and closes", async () => {
  const appended = installDom();
  const { showErrorModal } = await import("../lib/errors-ui.js");
  const clicks = [];
  showErrorModal({
    title: "t",
    body: "b",
    actions: [{ label: "重试", primary: true, onClick: () => clicks.push("retry") }],
  });
  const modal = appended[0];
  const actions = modal.children[".error-modal-actions"];
  const btn = Object.values(actions.children)[0];
  for (const fn of btn.listeners.get("click") || []) fn();
  assert.deepEqual(clicks, ["retry"]);
  assert.equal(modal.removed, true, "modal removed after action");
});

test("installCompatBanner creates a banner when hard APIs are missing", async () => {
  const appended = installDom();
  const { installCompatBanner } = await import("../lib/errors-ui.js");
  installCompatBanner();
  const banner = appended[0];
  assert.ok(banner.className.includes("compat-banner"));
  assert.ok(banner.innerHTML.includes("Chrome"));
  assert.ok(banner.innerHTML.includes("createImageBitmap"));
});
