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
  const emptyEl = { hidden: true };
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
  const batchEl = { textContent: "", title: "" };
  const zipRow = { hidden: true };
  const zipProgressEl = { attrs: {}, setAttribute(k, v) { this.attrs[k] = v; } };
  const zipBar = { style: { width: "0%" } };
  const zipPct = { textContent: "0%" };
  const zipName = { textContent: "打包" };
  c._q.set("tbody", tbody);
  c._q.set(".progress > i", bar);
  c._q.set(".progress", progressEl);
  c._q.set(".jobs-empty", emptyEl);
  c._q.set(".pct", pct);
  c._q.set('[data-act="cancel"]', cancelBtn);
  c._q.set(".batch", batchEl);
  c._q.set(".zip-progress", zipRow);
  c._q.set(".zip-progress .progress", zipProgressEl);
  c._q.set(".zip-progress .progress > i", zipBar);
  c._q.set(".zip-pct", zipPct);
  c._q.set(".zip-name", zipName);
  return { container: c, tbody, bar, progressEl, emptyEl, pct, cancelBtn, batchEl, zipRow, zipProgressEl, zipBar, zipPct, zipName };
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

test("setBatch shows current/total with filename and clamps", async () => {
  installDom();
  const { createJobList } = await import("../lib/joblist.js");
  const { container, batchEl } = makeContainer();
  const list = createJobList(container, {});
  list.setBatch(0, 3, "a.png");
  assert.equal(batchEl.textContent, "1/3 · a.png");
  assert.equal(batchEl.title, "a.png");
  list.setBatch(2, 3, "c.png");
  assert.equal(batchEl.textContent, "3/3 · c.png");
  list.setBatch(9, 3, "c.png");
  assert.equal(batchEl.textContent, "3/3 · c.png", "current clamped to total");
  list.setBatch(0, 0, "x.png");
  assert.equal(batchEl.textContent, "", "empty total clears the counter");
  list.setBatch(0, 3, "");
  assert.equal(batchEl.textContent, "", "missing name clears the counter");
  list.setBatch(0, 2, "a-very-long-filename-number-one-2026.png");
  assert.match(batchEl.textContent, /^1\/2 · /);
  assert.equal(batchEl.title, "a-very-long-filename-number-one-2026.png", "full name kept in title");
  assert.ok(batchEl.textContent.length < batchEl.title.length, "display name shortened");
  list.reset();
  assert.equal(batchEl.textContent, "");
});

test("zip progress renders on a separate bar without touching processing", async () => {
  installDom();
  const { createJobList } = await import("../lib/joblist.js");
  const { container, zipRow, zipBar, zipPct, zipName, zipProgressEl, bar, pct } = makeContainer();
  const list = createJobList(container, {});
  assert.equal(zipRow.hidden, true, "zip bar hidden until packing");
  list.setProgress(100);
  list.setZipProgress(45, "images.zip");
  assert.equal(zipRow.hidden, false);
  assert.equal(zipName.textContent, "打包 images.zip");
  assert.equal(zipBar.style.width, "45%");
  assert.equal(zipPct.textContent, "45%");
  assert.equal(zipProgressEl.attrs["aria-valuenow"], "45");
  assert.equal(bar.style.width, "100%", "processing bar untouched by zip progress");
  assert.equal(pct.textContent, "100%", "processing label untouched by zip progress");
  list.setZipProgress(250, "images.zip");
  assert.equal(zipPct.textContent, "100%", "clamped to 100");
  list.setZipProgress(-5, "images.zip");
  assert.equal(zipPct.textContent, "0%", "clamped to 0");
  list.setZipProgress(30);
  assert.equal(zipName.textContent, "打包 images.zip", "label kept when omitted");
  list.reset();
  assert.equal(zipRow.hidden, true, "hidden again for the next batch");
  assert.equal(zipBar.style.width, "0%");
  assert.equal(zipPct.textContent, "0%");
});

test("empty state shows when no jobs and hides after submit", async () => {
  installDom();
  const { createJobList } = await import("../lib/joblist.js");
  const { container, emptyEl } = makeContainer();
  const list = createJobList(container, {});
  assert.equal(emptyEl.hidden, false, "empty state visible with no jobs");
  list.submit(JOBS());
  assert.equal(emptyEl.hidden, true, "empty state hidden once jobs exist");
  list.reset();
  assert.equal(emptyEl.hidden, false, "empty state returns after reset");
});

test("failedIndices tracks failed jobs across batches", async () => {
  installDom();
  const { createJobList } = await import("../lib/joblist.js");
  const { container } = makeContainer();
  const list = createJobList(container, {});
  assert.deepEqual(list.failedIndices(), [], "empty list has no failures");
  list.submit([
    { id: 0, name: "a.png" },
    { id: 1, name: "b.png" },
    { id: 2, name: "c.png" },
  ]);
  assert.deepEqual(list.failedIndices(), [], "all pending");
  list.setStatus(1, "failed", "boom");
  list.setStatus(2, "done");
  assert.deepEqual(list.failedIndices(), [1], "only failed id");
  list.setStatus(2, "failed", "again");
  assert.deepEqual(list.failedIndices(), [1, 2], "insertion order preserved");
  list.setStatus(1, "done");
  assert.deepEqual(list.failedIndices(), [2], "recovered job leaves the list");
  list.submit([{ id: 0, name: "fresh.png" }]);
  assert.deepEqual(list.failedIndices(), [], "new batch clears history");
});

test("finish clears the cancel latch so a retry can start", async () => {
  installDom();
  const { createJobList } = await import("../lib/joblist.js");
  const { container, cancelBtn } = makeContainer();
  const list = createJobList(container, {});
  list.submit(JOBS());
  cancelBtn.click();
  assert.equal(list.cancelled, true);
  list.finish();
  assert.equal(list.cancelled, false, "finish re-arms cancelled for the next run");
  assert.equal(cancelBtn.disabled, true);
});
