import test from "node:test";
import assert from "node:assert/strict";

import { STATUS_TEXT } from "../lib/joblist.js";

test("status text matches desktop", () => {
  assert.equal(STATUS_TEXT.pending, "等待");
  assert.equal(STATUS_TEXT.running, "处理中");
  assert.equal(STATUS_TEXT.done, "完成");
  assert.equal(STATUS_TEXT.failed, "失败");
  assert.equal(STATUS_TEXT.cancelled, "已取消");
});

test("status table covers exactly the five job states", () => {
  assert.deepEqual(
    Object.keys(STATUS_TEXT).sort(),
    ["cancelled", "done", "failed", "pending", "running"],
  );
  for (const v of Object.values(STATUS_TEXT)) {
    assert.ok(typeof v === "string" && v.length > 0);
  }
});

// ---- minimal DOM fakes so createJobList runs under node:test ----

function fakeQueryable() {
  const queries = new Map();
  return {
    _q: queries,
    querySelector(sel) {
      return queries.get(sel) || null;
    },
  };
}

function makeContainer() {
  const tbody = {
    children: [],
    ...fakeQueryable(),
    appendChild(c) {
      this.children.push(c);
      return c;
    },
  };
  let tbodyHtml = "stale";
  Object.defineProperty(tbody, "innerHTML", {
    get: () => tbodyHtml,
    set(v) {
      tbodyHtml = v;
      tbody.children.length = 0;
    },
  });
  // mirror the state the real template markup would parse to
  const bar = { style: { width: "0%" } };
  const progressEl = { attrs: {}, setAttribute(k, v) { this.attrs[k] = v; } };
  const pct = { textContent: "0%" };
  const cancelBtn = {
    disabled: true, // template ships with the disabled attribute
    _listeners: new Map(),
    addEventListener(type, fn) {
      if (!this._listeners.has(type)) this._listeners.set(type, []);
      this._listeners.get(type).push(fn);
    },
    click() {
      for (const fn of this._listeners.get("click") || []) fn();
    },
  };
  const c = {
    innerHTML: "",
    ...fakeQueryable(),
  };
  c._q.set("tbody", tbody);
  c._q.set(".progress > i", bar);
  c._q.set(".progress", progressEl);
  c._q.set(".pct", pct);
  c._q.set('[data-act="cancel"]', cancelBtn);
  return { container: c, tbody, bar, progressEl, pct, cancelBtn };
}

function makeTr() {
  const cells = [
    {
      children: [],
      attrs: {},
      listeners: new Map(),
      appendChild(c) { this.children.push(c); return c; },
      setAttribute(k, v) { this.attrs[k] = v; },
      addEventListener(type, fn) {
        if (!this.listeners.has(type)) this.listeners.set(type, []);
        this.listeners.get(type).push(fn);
      },
      dispatch(type, ev) {
        for (const fn of this.listeners.get(type) || []) fn(ev);
      },
      innerHTML: "",
    },
    { textContent: "", innerHTML: "" },
    { className: "", textContent: "", title: "" },
  ];
  const tr = {
    cells,
    children: [],
    appendChild(c) { this.children.push(c); return c; },
    ...fakeQueryable(),
  };
  tr._q.set("td.status", cells[2]);
  Object.defineProperty(tr, "innerHTML", {
    get: () => "",
    set() {
      tr.cells = [
        {
          children: [],
          attrs: {},
          listeners: new Map(),
          appendChild(c) { this.children.push(c); return c; },
          setAttribute(k, v) { this.attrs[k] = v; },
          addEventListener(type, fn) {
            if (!this.listeners.has(type)) this.listeners.set(type, []);
            this.listeners.get(type).push(fn);
          },
          dispatch(type, ev) {
            for (const fn of this.listeners.get(type) || []) fn(ev);
          },
          innerHTML: "",
        },
        { textContent: "", innerHTML: "" },
        { className: "", textContent: "", title: "" },
      ];
      tr._q.set("td.status", tr.cells[2]);
    },
  });
  return tr;
}

function installDom() {
  const created = [];
  globalThis.document = {
    createElement(tag) {
      const el = tag === "tr" ? makeTr() : { src: "", alt: "", tag };
      created.push(el);
      return el;
    },
  };
  if (typeof globalThis.URL.revokeObjectURL !== "function") {
    globalThis.URL.revokeObjectURL = () => {};
  }
  return created;
}

const JOBS = () => [
  { id: 1, name: "a.png", thumb: "blob:a" },
  { id: 2, name: "b.gif" },
  { id: 3, name: "c.mp4", thumb: "blob:c" },
];

test("createJobList renders skeleton and starts idle", async () => {
  installDom();
  const { createJobList } = await import("../lib/joblist.js");
  const { container, cancelBtn, pct, bar } = makeContainer();
  const list = createJobList(container, {});
  assert.equal(list.cancelled, false);
  assert.equal(cancelBtn.disabled, true);
  assert.ok(container.innerHTML.includes('data-act="cancel"'));
  assert.ok(container.innerHTML.includes("<table"));
  assert.ok(container.innerHTML.includes("width:0%"));
  assert.equal(bar.style.width, "0%");
  assert.equal(pct.textContent, "0%");
});

test("submit builds rows, thumbs, and enables cancel", async () => {
  installDom();
  const { createJobList } = await import("../lib/joblist.js");
  const { container, tbody, cancelBtn } = makeContainer();
  const list = createJobList(container, {});
  list.submit(JOBS());
  assert.equal(tbody.children.length, 3);
  assert.equal(cancelBtn.disabled, false);
  const [r1, r2, r3] = tbody.children;
  assert.equal(r1.cells[1].textContent, "a.png");
  assert.equal(r2.cells[1].textContent, "b.gif");
  assert.equal(r1.cells[2].textContent, STATUS_TEXT.pending);
  assert.equal(r1.cells[2].className, "status st-pending");
  // thumbs only where provided
  assert.equal(r1.cells[0].children.length, 1);
  assert.equal(r1.cells[0].children[0].src, "blob:a");
  assert.equal(r2.cells[0].children.length, 0);
  assert.equal(r3.cells[0].children.length, 1);
  // unknown id is a no-op
  list.setStatus(99, "done");
  assert.equal(r1.cells[2].textContent, STATUS_TEXT.pending);
});

test("submit replaces previous rows via reset", async () => {
  installDom();
  const { createJobList } = await import("../lib/joblist.js");
  const { container, tbody, pct, bar, cancelBtn } = makeContainer();
  const list = createJobList(container, {});
  list.submit(JOBS());
  list.setProgress(66);
  list.submit([{ id: 9, name: "only.png" }]);
  assert.equal(tbody.children.length, 1);
  assert.equal(tbody.children[0].cells[1].textContent, "only.png");
  assert.equal(bar.style.width, "0%");
  assert.equal(pct.textContent, "0%");
  assert.equal(cancelBtn.disabled, false);
});

test("setStatus renders text, classes, and failure details", async () => {
  installDom();
  const { createJobList } = await import("../lib/joblist.js");
  const { container } = makeContainer();
  const list = createJobList(container, {});
  list.submit(JOBS());

  list.setStatus(1, "running");
  list.setStatus(1, "done");
  let td = container._q.get("tbody").children[0].cells[2];
  assert.equal(td.textContent, STATUS_TEXT.done);
  assert.equal(td.className, "status st-done");

  list.setStatus(1, "failed", "磁盘已满");
  assert.equal(td.textContent, `${STATUS_TEXT.failed}（磁盘已满）`);
  assert.equal(td.title, "磁盘已满");

  list.setStatus(1, "cancelled", "用户取消");
  assert.equal(td.textContent, `${STATUS_TEXT.cancelled}（用户取消）`);
  assert.equal(td.title, "用户取消");

  // unknown status falls back to the raw string
  list.setStatus(1, "weird");
  assert.equal(td.textContent, "weird");
  assert.equal(td.className, "status st-weird");

  // failed without detail keeps plain label (previous title persists)
  list.setStatus(1, "failed");
  assert.equal(td.textContent, STATUS_TEXT.failed);
  assert.equal(td.title, "用户取消");
});

test("setProgress clamps and updates label and bar", async () => {
  installDom();
  const { createJobList } = await import("../lib/joblist.js");
  const { container, pct, bar } = makeContainer();
  const list = createJobList(container, {});
  list.setProgress(-20);
  assert.equal(bar.style.width, "0%");
  assert.equal(pct.textContent, "0%");
  list.setProgress(42.7);
  assert.equal(bar.style.width, "42%");
  assert.equal(pct.textContent, "42%");
  list.setProgress(250);
  assert.equal(bar.style.width, "100%");
  assert.equal(pct.textContent, "100%");
});

test("cancel button toggles cancelled, invokes onCancel once, and re-arms on submit", async () => {
  installDom();
  const { createJobList } = await import("../lib/joblist.js");
  const { container, cancelBtn } = makeContainer();
  const calls = [];
  const list = createJobList(container, { onCancel: () => calls.push(1) });
  list.submit(JOBS());
  assert.equal(list.cancelled, false);
  cancelBtn.click();
  assert.equal(list.cancelled, true);
  assert.deepEqual(calls, [1]);
  assert.equal(cancelBtn.disabled, true, "cancel disables itself while the click is handled");
  cancelBtn.click();
  cancelBtn.click();
  assert.deepEqual(calls, [1], "double click does not re-trigger onCancel");
  // a new batch re-enables the button
  list.submit(JOBS());
  assert.equal(cancelBtn.disabled, false);
});

test("reset clears rows, releases thumbs, and re-arms cancel", async () => {
  installDom();
  const released = [];
  const origRevoke = globalThis.URL.revokeObjectURL;
  globalThis.URL.revokeObjectURL = (u) => released.push(u);
  try {
    const { createJobList } = await import("../lib/joblist.js");
    const { container, tbody, pct, bar, cancelBtn } = makeContainer();
    const list = createJobList(container, {});
    list.submit(JOBS());
    list.setProgress(80);
    cancelBtn.click();
    assert.equal(list.cancelled, true);

    list.reset();
    assert.equal(list.cancelled, false);
    assert.equal(tbody.children.length, 0);
    assert.equal(tbody.innerHTML, "");
    assert.equal(bar.style.width, "0%");
    assert.equal(pct.textContent, "0%");
    assert.equal(cancelBtn.disabled, true);
    assert.deepEqual(released.sort(), ["blob:a", "blob:c"]);
  } finally {
    if (origRevoke) globalThis.URL.revokeObjectURL = origRevoke;
    else delete globalThis.URL.revokeObjectURL;
  }
});

test("finish disables the cancel button", async () => {
  installDom();
  const { createJobList } = await import("../lib/joblist.js");
  const { container, cancelBtn } = makeContainer();
  const list = createJobList(container, {});
  list.submit(JOBS());
  assert.equal(cancelBtn.disabled, false);
  list.finish();
  assert.equal(cancelBtn.disabled, true);
});

test("progress bar exposes role=progressbar and tracks aria-valuenow", async () => {
  installDom();
  const { createJobList } = await import("../lib/joblist.js");
  const { container, progressEl } = makeContainer();
  createJobList(container, {});
  assert.match(container.innerHTML, /role="progressbar"/);
  assert.match(container.innerHTML, /aria-valuemin="0"/);
  assert.match(container.innerHTML, /aria-valuemax="100"/);
  assert.match(container.innerHTML, /aria-label="转换进度"/);
  assert.equal(progressEl.attrs["aria-valuenow"], undefined);
});

test("setProgress updates aria-valuenow on the progressbar element", async () => {
  installDom();
  const { createJobList } = await import("../lib/joblist.js");
  const { container, progressEl } = makeContainer();
  const list = createJobList(container, {});
  list.setProgress(45);
  assert.equal(progressEl.attrs["aria-valuenow"], "45");
  list.setProgress(140);
  assert.equal(progressEl.attrs["aria-valuenow"], "100", "clamped to the aria maximum");
  list.setProgress(-20);
  assert.equal(progressEl.attrs["aria-valuenow"], "0", "clamped to the aria minimum");
});

test("setOutputBlob makes the row thumb draggable with the output file", async () => {
  installDom();
  const { createJobList } = await import("../lib/joblist.js");
  const { container, tbody } = makeContainer();
  const list = createJobList(container, {});
  list.submit(JOBS());
  const thumb = tbody.children[0].cells[0];
  assert.equal(thumb.attrs.draggable, undefined);
  list.setOutputBlob(1, { blob: new Blob(["x"]), filename: "a.png" });
  assert.equal(thumb.attrs.draggable, "true");
  const ev = { dataTransfer: { items: { add() {} }, effectAllowed: "" } };
  thumb.dispatch("dragstart", ev);
  assert.equal(ev.dataTransfer.effectAllowed, "copy");
});

test("setOutputBlob ignores unknown ids", async () => {
  installDom();
  const { createJobList } = await import("../lib/joblist.js");
  const { container } = makeContainer();
  const list = createJobList(container, {});
  list.submit(JOBS());
  list.setOutputBlob(999, { blob: new Blob(["x"]), filename: "z.png" });
});
