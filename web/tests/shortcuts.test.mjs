// web/tests/shortcuts.test.mjs
import test from "node:test";
import assert from "node:assert/strict";

function fakeEl() {
  const el = {
    tagName: "div",
    className: "",
    innerHTML: "",
    attrs: {},
    listeners: new Map(),
    _open: false,
    classList: {
      toggle(c, on) {
        el._open = on;
      },
      remove() {
        el._open = false;
      },
      add() {},
    },
    setAttribute(k, v) {
      el.attrs[k] = v;
    },
    getAttribute(k) {
      return k in el.attrs ? el.attrs[k] : null;
    },
    addEventListener(type, fn) {
      if (!el.listeners.has(type)) el.listeners.set(type, []);
      el.listeners.get(type).push(fn);
    },
    appendChild() {},
    querySelector() {
      return { addEventListener() {} };
    },
  };
  return el;
}

function installDom() {
  const listeners = new Map();
  globalThis.window = {
    addEventListener(type, fn) {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(fn);
    },
    _fire(type, ev) {
      for (const fn of listeners.get(type) || []) fn(ev);
    },
    _listeners: listeners,
  };
  globalThis.document = {
    createElement: () => fakeEl(),
    body: { appendChild() {} },
  };
}

test("installGlobalShortcuts dispatches registered actions for Ctrl shortcuts", async () => {
  installDom();
  const { installGlobalShortcuts, registerShortcutAction, clearShortcutActions } = await import(
    "../lib/shortcuts.js"
  );
  const calls = [];
  registerShortcutAction("onOpen", () => calls.push("open"));
  registerShortcutAction("onStart", () => calls.push("start"));
  registerShortcutAction("onDownload", () => calls.push("download"));
  registerShortcutAction("onCancel", () => calls.push("cancel"));
  installGlobalShortcuts();
  const fire = (ev) => globalThis.window._fire("keydown", ev);
  const mod = { ctrlKey: true, metaKey: false, preventDefault() {} };
  fire({ key: "o", ...mod });
  fire({ key: "Enter", ...mod });
  fire({ key: "s", ...mod });
  fire({ key: "Escape", ctrlKey: false, metaKey: false, preventDefault() {} });
  assert.deepEqual(calls, ["open", "start", "download", "cancel"]);
  clearShortcutActions();
});

test("shortcuts ignore plain keys and inputs", async () => {
  installDom();
  const { installGlobalShortcuts, registerShortcutAction, clearShortcutActions } = await import(
    "../lib/shortcuts.js"
  );
  const calls = [];
  registerShortcutAction("onStart", () => calls.push("start"));
  installGlobalShortcuts();
  const fire = (ev) => globalThis.window._fire("keydown", ev);
  fire({ key: "Enter", ctrlKey: false, metaKey: false, preventDefault() {} });
  fire({ key: "o", ctrlKey: false, metaKey: false, preventDefault() {} });
  fire({ key: "Enter", ctrlKey: true, metaKey: false, target: { tagName: "INPUT" }, preventDefault() {} });
  assert.deepEqual(calls, [], "plain keys and input-focused shortcuts do nothing");
  clearShortcutActions();
});

test("metaKey counts as modifier", async () => {
  installDom();
  const { installGlobalShortcuts, registerShortcutAction, clearShortcutActions } = await import(
    "../lib/shortcuts.js"
  );
  const calls = [];
  registerShortcutAction("onOpen", () => calls.push("open"));
  installGlobalShortcuts();
  globalThis.window._fire("keydown", {
    key: "o",
    ctrlKey: false,
    metaKey: true,
    preventDefault() {},
  });
  assert.deepEqual(calls, ["open"]);
  clearShortcutActions();
});

test("Escape closes the help panel before cancelling", async () => {
  installDom();
  const {
    installGlobalShortcuts,
    registerShortcutAction,
    clearShortcutActions,
    toggleShortcutHelp,
    hideShortcutHelp,
    isShortcutHelpVisible,
  } = await import("../lib/shortcuts.js");
  const cancels = [];
  registerShortcutAction("onCancel", () => cancels.push("cancel"));
  installGlobalShortcuts();
  const fire = (ev) => globalThis.window._fire("keydown", ev);
  toggleShortcutHelp();
  assert.equal(isShortcutHelpVisible(), true);
  fire({ key: "Escape", ctrlKey: false, metaKey: false, preventDefault() {} });
  assert.equal(isShortcutHelpVisible(), false, "Escape closes the help panel");
  assert.deepEqual(cancels, [], "no cancel while closing help");
  fire({ key: "Escape", ctrlKey: false, metaKey: false, preventDefault() {} });
  assert.deepEqual(cancels, ["cancel"], "Escape cancels once help is closed");
  hideShortcutHelp();
  clearShortcutActions();
});

test("? toggles the shortcut help panel", async () => {
  installDom();
  const { toggleShortcutHelp, hideShortcutHelp, isShortcutHelpVisible } = await import(
    "../lib/shortcuts.js"
  );
  toggleShortcutHelp();
  assert.equal(isShortcutHelpVisible(), true);
  toggleShortcutHelp();
  assert.equal(isShortcutHelpVisible(), false);
  hideShortcutHelp();
});
