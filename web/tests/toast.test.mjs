// web/tests/toast.test.mjs
import test from "node:test";
import assert from "node:assert/strict";

function fakeEl() {
  const el = {
    tagName: "div",
    className: "",
    innerHTML: "",
    children: {},
    listeners: new Map(),
    classList: { add() {}, remove() {} },
    setAttribute() {},
    appendChild(c) {
      el.children[c.className || Object.keys(el.children).length] = c;
    },
    querySelector(sel) {
      if (!el.children[sel]) el.children[sel] = fakeEl();
      return el.children[sel];
    },
    remove() {},
    addEventListener(type, fn) {
      if (!el.listeners.has(type)) el.listeners.set(type, []);
      el.listeners.get(type).push(fn);
    },
  };
  Object.defineProperty(el, "textContent", {
    get() {
      return el._text || "";
    },
    set(v) {
      el._text = v;
    },
  });
  return el;
}

let sharedBody = null;
function installDom() {
  if (!sharedBody) {
    sharedBody = fakeEl();
    globalThis.document = { createElement: () => fakeEl(), body: sharedBody };
  }
  return sharedBody;
}

test("showToast creates a typed toast with icon and message", async () => {
  const body = installDom();
  const { showToast } = await import("../lib/toast.js");
  showToast("转换完成", "success");
  const container = body.children["toast-container"];
  assert.ok(container, "toast container appended to body");
  const toast = Object.values(container.children).find((c) => c.className.includes("toast-success"));
  assert.ok(toast, "a success toast was appended");
  assert.equal(toast.children[".toast-msg"]._text, "转换完成");
  assert.ok(toast.innerHTML.includes("✅"));
});

test("showToast defaults to info type", async () => {
  const body = installDom();
  const { showToast } = await import("../lib/toast.js");
  showToast("你好");
  const container = body.children["toast-container"];
  const toast = Object.values(container.children).find((c) => c.className.includes("toast-info"));
  assert.ok(toast, "an info toast was appended");
  assert.ok(toast.innerHTML.includes("ℹ️"));
});

test("toast close button is wired", async () => {
  const body = installDom();
  const { showToast } = await import("../lib/toast.js");
  showToast("可关闭", "warning");
  const container = body.children["toast-container"];
  const toast = Object.values(container.children).find((c) => c.className.includes("toast-warning"));
  assert.ok(toast);
  const closeBtn = toast.children[".toast-close"];
  assert.equal(closeBtn.listeners.has("click"), true);
});
