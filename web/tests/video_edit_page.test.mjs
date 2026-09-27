// web/tests/video_edit_page.test.mjs
// 视频编辑页交互逻辑测试：用 mock DOM 驱动 mountVideoEdit，
// 覆盖拖拽添加、选中、参数调整、拆分、删除、移动、裁剪、播放预览、导出。
import test from "node:test";
import assert from "node:assert/strict";

const rafQueue = [];
function fakeRaf(fn) {
  rafQueue.push(fn);
  return rafQueue.length;
}
function runRaf(ts) {
  const cbs = rafQueue.splice(0);
  for (const fn of cbs) fn(ts);
}
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

const ctxStub = {
  calls: [],
  clearRect(...a) { ctxStub.calls.push(["clearRect", ...a]); },
  drawImage(...a) { ctxStub.calls.push(["drawImage", ...a]); },
  fillText(...a) { ctxStub.calls.push(["fillText", ...a]); },
  save() {},
  restore() {},
  font: "",
  fillStyle: "",
  globalAlpha: 1,
};

function makeClassList() {
  const set = new Set();
  return {
    add: (...cs) => cs.forEach((c) => set.add(c)),
    remove: (...cs) => cs.forEach((c) => set.delete(c)),
    toggle: (c, force) => {
      const on = force === undefined ? !set.has(c) : force;
      if (on) set.add(c);
      else set.delete(c);
    },
    contains: (c) => set.has(c),
  };
}

function makeEl(tag = "div") {
  const listeners = {};
  const el = {
    tagName: String(tag).toUpperCase(),
    children: [],
    style: {},
    dataset: {},
    classList: makeClassList(),
    _listeners: listeners,
    parentNode: null,
    textContent: "",
    value: "",
    checked: false,
    hidden: false,
    disabled: false,
    draggable: false,
    files: [],
    className: "",
    id: "",
    addEventListener(type, fn) {
      (listeners[type] ||= []).push(fn);
    },
    removeEventListener(type, fn) {
      const l = listeners[type];
      if (l) {
        const i = l.indexOf(fn);
        if (i >= 0) l.splice(i, 1);
      }
    },
    fire(type, ev = {}) {
      const event = Object.assign({ type, target: el, preventDefault() {} }, ev);
      event.stopPropagation = () => {
        event._stop = true;
      };
      let node = el;
      while (node) {
        const nodeListeners = node._listeners || {};
        for (const fn of [...(nodeListeners[type] || [])]) fn(event);
        if (event._stop) break;
        node = node.parentNode;
      }
      return event;
    },
    click() {
      return el.fire("click");
    },
    appendChild(child) {
      child.parentNode = el;
      el.children.push(child);
      return child;
    },
    removeChild(child) {
      const i = el.children.indexOf(child);
      if (i >= 0) el.children.splice(i, 1);
      child.parentNode = null;
      return child;
    },
    remove() {
      if (el.parentNode) el.parentNode.removeChild(el);
    },
    setAttribute(name, value) {
      el.dataset[name] = String(value);
    },
    getAttribute(name) {
      return el.dataset[name] ?? null;
    },
    removeAttribute(name) {
      delete el.dataset[name];
    },
    setPointerCapture() {},
    releasePointerCapture() {},
    getBoundingClientRect() {
      return { left: 0, top: 0, right: 1000, bottom: 40, width: 1000, height: 40 };
    },
    querySelector(sel) {
      return queryAll(el, sel)[0] || null;
    },
    querySelectorAll(sel) {
      return queryAll(el, sel);
    },
    set innerHTML(v) {
      el.children = [];
      el._html = v;
    },
    get innerHTML() {
      return el._html || "";
    },
  };
  if (tag === "canvas") {
    el.width = 1280;
    el.height = 720;
    el.getContext = () => ctxStub;
  }
  if (tag === "video") {
    let ct = 0;
    let srcUrl = "";
    el.duration = globalThis.__FAKE_VIDEO_DURATION ?? 10;
    el.muted = false;
    el.preload = "";
    el.load = () => {};
    Object.defineProperty(el, "currentTime", {
      get: () => ct,
      set: (v) => {
        ct = v;
        queueMicrotask(() => el.fire("seeked"));
      },
    });
    Object.defineProperty(el, "src", {
      get: () => srcUrl,
      set: (v) => {
        srcUrl = v;
        queueMicrotask(() => {
          if (typeof el.onloadedmetadata === "function") el.onloadedmetadata();
        });
      },
    });
  }
  return el;
}

function queryAll(root, sel) {
  const out = [];
  const match = (node) => {
    if (sel.startsWith("#")) return node.id === sel.slice(1);
    if (sel.startsWith(".")) return String(node.className || "").split(/\s+/).includes(sel.slice(1));
    return node.tagName === sel.toUpperCase();
  };
  const walk = (node) => {
    for (const child of node.children || []) {
      if (match(child)) out.push(child);
      walk(child);
    }
  };
  walk(root);
  return out;
}

const docListeners = {};
const bodyEl = makeEl("body");
const statusEl = makeEl("span");
const appRoot = makeEl("div");
const appGeneric = makeEl("div");
appRoot.querySelector = () => appGeneric;

const documentFake = {
  createElement: (tag) => makeEl(tag),
  addEventListener(type, fn) {
    (docListeners[type] ||= []).push(fn);
  },
  removeEventListener() {},
  fireDoc(type, ev = {}) {
    const event = Object.assign({ type, preventDefault() {}, stopPropagation() {} }, ev);
    for (const fn of [...(docListeners[type] || [])]) fn(event);
  },
  getElementById(id) {
    if (id === "app") return appRoot;
    if (id === "status") return statusEl;
    return null;
  },
  querySelectorAll() {
    return [];
  },
  body: bodyEl,
};

let objectUrlCount = 0;

function installGlobals() {
  globalThis.document = documentFake;
  globalThis.window = { addEventListener() {} };
  globalThis.location = { hash: "#/" };
  globalThis.localStorage = { getItem: () => "1", setItem() {} };
  globalThis.createImageBitmap = async () => ({});
  globalThis.OffscreenCanvas = class OffscreenCanvas {};
  const origCreate = globalThis.URL.createObjectURL;
  const origRevoke = globalThis.URL.revokeObjectURL;
  globalThis.URL.createObjectURL = () => `blob:fake/${++objectUrlCount}`;
  globalThis.URL.revokeObjectURL = () => {};
  return () => {
    globalThis.URL.createObjectURL = origCreate;
    globalThis.URL.revokeObjectURL = origRevoke;
  };
}

function makeRoot() {
  const registry = new Map();
  registry.set("#previewCanvas", makeEl("canvas"));
  const root = makeEl("div");
  root.querySelector = (sel) => {
    if (!registry.has(sel)) registry.set(sel, makeEl("div"));
    return registry.get(sel);
  };
  return root;
}

installGlobals();
const { mountVideoEdit } = await import("../pages/video_edit.js");

function fakeFile(name, size = 1000) {
  return { name, size, type: "video/mp4" };
}

async function setupEditor(extraDeps = {}) {
  const root = makeRoot();
  const handle = mountVideoEdit(root, { requestAnimationFrame: fakeRaf, ...extraDeps });
  runRaf(0);
  await flush();
  return { root, handle, els: handle.els };
}

async function addFileViaInput(els, file) {
  els.files.files = [file];
  els.files.fire("change");
  await flush();
}

function videoLane(els) {
  return els.tracks.children[0].children[1];
}

function firstClipEl(els) {
  return videoLane(els).children[0];
}

function dropFileOnTimeline(els, index) {
  const dt = { data: {}, setData(t, v) { this.data[t] = v; }, effectAllowed: "" };
  els.fileList.children[index].fire("dragstart", { dataTransfer: dt });
  els.timeline.fire("drop", { dataTransfer: { files: [] } });
  return dt;
}

test("mount 渲染三轨、时间刻度与占位提示", () => {
  return setupEditor().then(({ els }) => {
    assert.equal(els.tracks.querySelectorAll(".tl-track").length, 3);
    assert.equal(els.ruler.children.length, 11);
    assert.equal(els.paramsBody.children[0].textContent, "选择时间线上的片段");
    assert.equal(els.canvas.width, 640);
    assert.equal(els.timeInfo.textContent, "00:00 / 00:00");
  });
});

test("添加文件显示在文件库并探测时长", async () => {
  const { els } = await setupEditor();
  await addFileViaInput(els, fakeFile("a.mp4"));
  assert.equal(els.fileList.children.length, 1);
  assert.equal(els.fileList.children[0].children[0].textContent, "a.mp4");
  assert.equal(els.fileList.children[0].children[1].textContent, "00:10");
});

test("不支持的文件类型报错", async () => {
  const { els } = await setupEditor();
  await addFileViaInput(els, fakeFile("note.txt"));
  assert.equal(els.fileList.children.length, 0);
  assert.ok(els.err.textContent.includes("不支持的文件类型"));
});

test("拖拽文件到时间线创建片段", async () => {
  const { handle, els } = await setupEditor();
  await addFileViaInput(els, fakeFile("a.mp4"));
  const dt = dropFileOnTimeline(els, 0);
  assert.equal(dt.data["text/plain"], "0");
  assert.equal(videoLane(els).children.length, 1);
  const clipEl = firstClipEl(els);
  assert.ok(clipEl.className.includes("tl-clip"));
  assert.ok(clipEl.className.includes("selected"));
  assert.equal(clipEl.children[0].textContent, "a.mp4");
  const clips = handle.timeline.tracks[0].clips;
  assert.equal(clips.length, 1);
  assert.equal(clips[0].timelineIn, 0);
  assert.equal(clips[0].sourceOut, 10);
});

test("点击片段选中后参数面板显示全部控件", async () => {
  const { els } = await setupEditor();
  await addFileViaInput(els, fakeFile("a.mp4"));
  dropFileOnTimeline(els, 0);
  const clipEl = firstClipEl(els);
  clipEl.fire("click");
  for (const id of [
    "speed", "volume", "fadeIn", "fadeOut",
    "rotation", "flipH", "flipV", "scale", "cropOn", "cropX", "cropY", "cropW", "cropH",
    "brightness", "contrast", "saturation", "hue", "grayscale", "sepia", "blur", "sharpen",
    "overlayOn", "overlayText", "overlaySize", "overlayColor", "overlayX", "overlayY", "overlayOpacity",
  ]) {
    assert.ok(els.paramsBody.querySelector(`#${id}`), `缺少控件 #${id}`);
  }
  assert.equal(els.paramsBody.querySelectorAll(".field").length, 28);
});

test("参数调整通过 AdjustParamsCommand 更新模型", async () => {
  const { handle, els } = await setupEditor();
  await addFileViaInput(els, fakeFile("a.mp4"));
  dropFileOnTimeline(els, 0);
  const clip = handle.timeline.tracks[0].clips[0];
  const speedInput = els.paramsBody.querySelector("#speed");
  speedInput.value = "2";
  speedInput.fire("input");
  assert.equal(clip.speed, 2);
  assert.equal(handle.engine.undoStack.length, 1);
  assert.equal(firstClipEl(els).style.width, "50%");
});

test("双击片段在播放头处拆分", async () => {
  const { handle, els } = await setupEditor();
  await addFileViaInput(els, fakeFile("a.mp4"));
  dropFileOnTimeline(els, 0);
  videoLane(els).fire("pointerdown", { clientX: 400 });
  assert.equal(handle.state.currentTime, 4);
  firstClipEl(els).fire("dblclick");
  const clips = handle.timeline.tracks[0].clips;
  assert.equal(clips.length, 2);
  assert.equal(clips[0].sourceOut, 4);
  assert.equal(clips[1].sourceIn, 4);
  assert.equal(clips[1].timelineIn, 4);
});

test("播放头不在片段内时双击不拆分", async () => {
  const { handle, els } = await setupEditor();
  await addFileViaInput(els, fakeFile("a.mp4"));
  dropFileOnTimeline(els, 0);
  videoLane(els).fire("pointerdown", { clientX: 0 });
  firstClipEl(els).fire("dblclick");
  assert.equal(handle.timeline.tracks[0].clips.length, 1);
  assert.ok(els.err.textContent.includes("播放头不在片段内"));
});

test("Delete 键删除选中片段", async () => {
  const { handle, els } = await setupEditor();
  await addFileViaInput(els, fakeFile("a.mp4"));
  dropFileOnTimeline(els, 0);
  documentFake.fireDoc("keydown", { key: "Delete", target: { tagName: "DIV" } });
  assert.equal(handle.timeline.tracks[0].clips.length, 0);
  assert.equal(handle.state.selectedClipId, null);
  assert.equal(els.paramsBody.children[0].textContent, "选择时间线上的片段");
});

test("右键菜单删除片段", async () => {
  const { handle, els } = await setupEditor();
  await addFileViaInput(els, fakeFile("a.mp4"));
  dropFileOnTimeline(els, 0);
  firstClipEl(els).fire("contextmenu", {});
  const menu = bodyEl.querySelector(".clip-menu");
  assert.ok(menu);
  assert.equal(menu.children.length, 2);
  assert.equal(menu.children[0].textContent, "拆分");
  assert.equal(menu.children[1].textContent, "删除");
  menu.children[1].fire("click");
  assert.equal(handle.timeline.tracks[0].clips.length, 0);
});

test("撤销与重做按钮恢复片段", async () => {
  const { handle, els } = await setupEditor();
  await addFileViaInput(els, fakeFile("a.mp4"));
  dropFileOnTimeline(els, 0);
  documentFake.fireDoc("keydown", { key: "Delete", target: { tagName: "DIV" } });
  assert.equal(handle.timeline.tracks[0].clips.length, 0);
  els.undoBtn.fire("click");
  assert.equal(handle.timeline.tracks[0].clips.length, 1);
  els.redoBtn.fire("click");
  assert.equal(handle.timeline.tracks[0].clips.length, 0);
});

test("拖拽片段在轨道内移动", async () => {
  globalThis.__FAKE_VIDEO_DURATION = 5;
  try {
    const { handle, els } = await setupEditor();
    await addFileViaInput(els, fakeFile("a.mp4"));
    dropFileOnTimeline(els, 0);
    const clip = handle.timeline.tracks[0].clips[0];
    const clipEl = firstClipEl(els);
    clipEl.fire("pointerdown", { clientX: 100 });
    clipEl.fire("pointermove", { clientX: 300 });
    assert.equal(clipEl.style.left, "20%");
    clipEl.fire("pointerup");
    assert.equal(clip.timelineIn, 2);
    assert.equal(handle.engine.undoStack.length, 1);
  } finally {
    delete globalThis.__FAKE_VIDEO_DURATION;
  }
});

test("拖拽右边缘裁剪片段", async () => {
  const { handle, els } = await setupEditor();
  await addFileViaInput(els, fakeFile("a.mp4"));
  dropFileOnTimeline(els, 0);
  const clip = handle.timeline.tracks[0].clips[0];
  const trimR = firstClipEl(els).children[2];
  trimR.fire("pointerdown", { clientX: 500 });
  trimR.fire("pointermove", { clientX: 400 });
  trimR.fire("pointerup");
  assert.equal(clip.sourceOut, 9);
});

test("播放与暂停驱动播放头和预览", async () => {
  const { handle, els } = await setupEditor();
  await addFileViaInput(els, fakeFile("a.mp4"));
  dropFileOnTimeline(els, 0);
  els.playBtn.fire("click");
  assert.equal(els.playBtn.textContent, "⏸");
  assert.equal(handle.state.playing, true);
  runRaf(1000);
  runRaf(2000);
  assert.equal(els.timeInfo.textContent, "00:01 / 00:10");
  await flush();
  assert.ok(ctxStub.calls.some((c) => c[0] === "drawImage"));
  els.playBtn.fire("click");
  assert.equal(els.playBtn.textContent, "▶");
  assert.equal(handle.state.playing, false);
});

test("空格键切换播放暂停", async () => {
  const { handle, els } = await setupEditor();
  await addFileViaInput(els, fakeFile("a.mp4"));
  dropFileOnTimeline(els, 0);
  documentFake.fireDoc("keydown", { key: " ", target: { tagName: "DIV" } });
  assert.equal(handle.state.playing, true);
  documentFake.fireDoc("keydown", { key: " ", target: { tagName: "DIV" } });
  assert.equal(handle.state.playing, false);
});

test("导出对话框收集选项并用 ExportOrchestrator 导出", async () => {
  const execCalls = [];
  const writes = {};
  const fakeFF = {
    exec: async (args) => {
      execCalls.push(args);
      return 0;
    },
    writeFile: async (name, content) => {
      writes[name] = content;
    },
    readFile: async () => new Uint8Array([1, 2, 3]),
    deleteFile: async () => {},
  };
  const { handle, els } = await setupEditor({ ensureFFmpeg: async () => fakeFF });
  await addFileViaInput(els, fakeFile("a.mp4"));
  dropFileOnTimeline(els, 0);
  await addFileViaInput(els, fakeFile("b.mp4"));
  dropFileOnTimeline(els, 1);
  assert.equal(handle.timeline.tracks[0].clips.length, 2);

  els.exportBtn.fire("click");
  const overlay = bodyEl.querySelector(".export-overlay");
  assert.ok(overlay);
  const dialog = overlay.children[0];
  assert.equal(dialog.querySelector("#fmt").value, "mp4");
  dialog.querySelector("#codec").value = "libx264";
  dialog.querySelector("#crf").value = "28";
  dialog.querySelector("#preset").value = "veryfast";
  dialog.querySelector("#exportGo").fire("click");
  for (let i = 0; i < 10; i++) await flush();

  const concatText = new TextDecoder().decode(writes["concat.txt"]);
  assert.equal(concatText, "file 'src_0.mp4'\nfile 'src_1.mp4'");
  assert.equal(execCalls.length, 1);
  assert.ok(execCalls[0].includes("concat.txt"));
  assert.ok(execCalls[0].includes("-crf"));
  assert.ok(execCalls[0].includes("28"));
  assert.equal(bodyEl.querySelector(".export-overlay"), null);
  assert.equal(els.err.textContent, "");
});

test("空时间线导出报错", async () => {
  const { els } = await setupEditor();
  els.exportBtn.fire("click");
  const dialog = bodyEl.querySelector(".export-overlay").children[0];
  dialog.querySelector("#exportGo").fire("click");
  assert.ok(els.err.textContent.includes("时间线上没有片段"));
});
