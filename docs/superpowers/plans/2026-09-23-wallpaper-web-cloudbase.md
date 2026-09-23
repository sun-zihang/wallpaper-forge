# Wallpaper Web (Cloudflare Pages) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a pure-static web app under `web/` that covers image convert/edit, GIF tools, WE unpack, and video (ffmpeg.wasm), deployable to Cloudflare Pages, with watermark removal linking to the desktop app.

**Architecture:** Native ES modules, no bundler. All processing runs in the browser. Heavy libs (ffmpeg.wasm, JSZip, gifuct-js) load from pinned CDNs on demand. `web/lib/*` ports semantics from desktop `core/*` (same Chinese errors and limits). Tasks are local job lists that produce Blobs/zip downloads; nothing is uploaded.

**Tech Stack:** HTML/CSS/ES modules, Canvas, ffmpeg.wasm, gifuct-js, JSZip, node:test for pure-logic tests, Cloudflare Pages (static).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-23-wallpaper-web-cloudbase-design.md`
- No Cloudflare Workers/R2/backend; files never leave the browser.
- No bundler; `web/` is the Pages root directory.
- CDN pins (exact):
  - JSZip: `https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js`
  - gifuct-js: `https://cdn.jsdelivr.net/npm/gifuct-js@2.1.2/dist/gifuct-js.min.js` (UMD global `gifuct`)
  - ffmpeg.wasm: `@ffmpeg/ffmpeg@0.12.10` + `@ffmpeg/util@0.12.1` from jsDelivr (corePath pinned in `video_bridge.js`)
- Video limits: `MAX_VIDEO_BYTES = 100 * 1024 * 1024`, `MAX_VIDEO_SECONDS = 300`.
- Chinese UX copy and status words match desktop: `等待` / `处理中` / `完成` / `失败` / `已取消`.
- Desktop `python -m pytest -q` must stay green after every commit that touches non-`web/` paths (and ideally never needs non-web changes for this plan).
- Identity for git: `sun-zihang <sun-zihang@users.noreply.github.com>`. Proxy when pushing: `$env:HTTPS_PROXY=$env:HTTP_PROXY="http://127.0.0.1:7897"`.
- Plan path: `docs/superpowers/plans/2026-09-23-wallpaper-web-cloudbase.md`

---

### Task 1: Scaffold `web/` shell, router, styles, home page

**Files:**
- Create: `web/index.html`
- Create: `web/styles.css`
- Create: `web/app.js`
- Create: `web/pages/home.js`
- Create: `web/tests/shell.test.mjs`

**Interfaces:**
- Consumes: none
- Produces: `window.App.route(name)` navigates views; DOM container `#app`; export `WEB_VERSION` from `web/version.js`; home page exports `mountHome(root)`.

- [ ] **Step 1: Write the failing test**

```js
// web/tests/shell.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { WEB_VERSION } from "../version.js";

test("web version semver-ish", () => {
  assert.match(WEB_VERSION, /^\d+\.\d+\.\d+$/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test web/tests/shell.test.mjs`  
Expected: FAIL (`Cannot find module '../version.js'`)

- [ ] **Step 3: Write minimal implementation**

```js
// web/version.js
export const WEB_VERSION = "0.6.0";
```

```html
<!-- web/index.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Wallpaper Converter Web</title>
  <link rel="stylesheet" href="./styles.css" />
</head>
<body>
  <header class="top">
    <a href="#/" class="brand">Wallpaper Converter</a>
    <nav>
      <a href="#/image">图片</a>
      <a href="#/gif">GIF</a>
      <a href="#/video">视频</a>
      <a href="#/unpack">解包</a>
    </nav>
    <span id="status" class="status">就绪</span>
  </header>
  <main id="app"></main>
  <script type="module" src="./app.js"></script>
</body>
</html>
```

```css
/* web/styles.css — dark, high contrast, similar spirit to desktop */
:root {
  --bg: #0f1115;
  --panel: #171a21;
  --border: #2a2f3a;
  --text: #e6e9ef;
  --muted: #9aa3b2;
  --accent: #3b82f6;
  --ok: #4ade80;
  --fail: #f87171;
  --run: #fbbf24;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Segoe UI", system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
}
.top {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 10px 16px;
  background: var(--panel);
  border-bottom: 1px solid var(--border);
}
.top nav a {
  color: var(--muted);
  margin-right: 12px;
  text-decoration: none;
}
.top nav a:hover { color: var(--text); }
.brand { color: var(--text); font-weight: 600; text-decoration: none; }
.status { margin-left: auto; color: var(--muted); font-size: 13px; }
#app { padding: 16px; max-width: 1100px; margin: 0 auto; }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  text-decoration: none;
  color: var(--text);
}
.card:hover { border-color: var(--accent); }
.card small { display: block; color: var(--muted); margin-top: 6px; }
.note {
  margin-top: 16px;
  padding: 12px;
  border: 1px dashed var(--border);
  border-radius: 8px;
  color: var(--muted);
}
.note a { color: var(--accent); }
.btn {
  background: var(--accent);
  border: 0;
  color: #fff;
  padding: 8px 14px;
  border-radius: 8px;
  cursor: pointer;
}
.btn.secondary { background: #2a2f3a; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.progress { height: 8px; background: #111; border-radius: 4px; overflow: hidden; margin-top: 8px; }
.progress > i { display: block; height: 100%; background: var(--accent); width: 0; }
table.jobs { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 14px; }
table.jobs th, table.jobs td { border-bottom: 1px solid var(--border); padding: 8px; text-align: left; }
.st-done { color: var(--ok); }
.st-failed { color: var(--fail); }
.st-running { color: var(--run); }
.st-cancelled, .st-pending { color: var(--muted); }
.row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 10px 0; }
label { color: var(--muted); font-size: 14px; }
input, select { background: #0c0e12; color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px; }
pre.err { color: var(--fail); white-space: pre-wrap; font-size: 12px; }
```

```js
// web/app.js
import { mountHome } from "./pages/home.js";

const routes = {
  "": mountHome,
  "/": mountHome,
};

const lazy = {
  "/image": () => import("./pages/image.js").then((m) => m.mountImage),
  "/gif": () => import("./pages/gif.js").then((m) => m.mountGif),
  "/video": () => import("./pages/video.js").then((m) => m.mountVideo),
  "/unpack": () => import("./pages/unpack.js").then((m) => m.mountUnpack),
};

export function setStatus(text) {
  const el = document.getElementById("status");
  if (el) el.textContent = text;
}

async function render() {
  const hash = location.hash.replace(/^#/, "") || "/";
  const root = document.getElementById("app");
  root.innerHTML = "";
  try {
    if (routes[hash]) {
      routes[hash](root);
      return;
    }
    if (lazy[hash]) {
      const mount = await lazy[hash]();
      mount(root);
      return;
    }
    location.hash = "#/";
  } catch (e) {
    root.innerHTML = `<pre class="err"></pre>`;
    root.querySelector("pre").textContent = String(e);
  }
}

window.addEventListener("hashchange", render);
render();
```

```js
// web/pages/home.js
export function mountHome(root) {
  root.innerHTML = `
    <div class="cards">
      <a class="card" href="#/image">图片转换<small>互转 / 缩放 / 裁剪 / 水印</small></a>
      <a class="card" href="#/gif">GIF 工具<small>拆帧 / 合帧</small></a>
      <a class="card" href="#/video">视频<small>互转 / 转 GIF / 截帧 / 片段（引擎按需加载）</small></a>
      <a class="card" href="#/unpack">解包<small>.pkg / .tex / .mpkg</small></a>
    </div>
    <div class="note">
      去水印（图片修复 / 视频 delogo）仅桌面版：
      <a href="https://github.com/sun-zihang/wallpaper-forge/releases" target="_blank" rel="noopener">下载桌面版</a>。
      所有文件仅在本机浏览器处理，不会上传。
    </div>
  `;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test web/tests/shell.test.mjs`  
Expected: PASS

- [ ] **Step 5: Open shell manually**

Run: open `web/index.html` via any static server, e.g. `python -m http.server 8765 -d web`  
Expected: home cards visible; `#/image` 404s to `#/` until later tasks (hash unknown → home) — acceptable until Task 7.

- [ ] **Step 6: Commit**

```bash
git add web/version.js web/tests/shell.test.mjs web/index.html web/styles.css web/app.js web/pages/home.js
git commit -m "feat(web): scaffold shell, router, home page"
```

---

### Task 2: Shared errors, job list, download helpers

**Files:**
- Create: `web/lib/errors.js`
- Create: `web/lib/download.js`
- Create: `web/lib/joblist.js`
- Create: `web/tests/errors.test.mjs`
- Create: `web/tests/joblist.test.mjs`

**Interfaces:**
- Consumes: none
- Produces:
  - `friendlyError(e) -> string`
  - `downloadBlob(blob, filename) -> void`
  - `createJobList(container, { onCancel }) -> { submit(jobs), setProgress(id, pct), setStatus(id, status, detail), get cancelled() }` where `job = { id, name }` and status ∈ pending|running|done|failed|cancelled.

- [ ] **Step 1: Write the failing tests**

```js
// web/tests/errors.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { friendlyError, AppError } from "../lib/errors.js";

test("friendlyError maps AppError", () => {
  assert.equal(friendlyError(new AppError("图片处理失败", "无法读取图片")), "图片处理失败：无法读取图片");
});

test("friendlyError unknown", () => {
  assert.match(friendlyError(new Error("boom")), /未知错误/);
});
```

```js
// web/tests/joblist.test.mjs
import test from "node:test";
import assert from "node:assert/strict";

// Pure status text table (extracted for testability)
import { STATUS_TEXT } from "../lib/joblist.js";

test("status text matches desktop", () => {
  assert.equal(STATUS_TEXT.pending, "等待");
  assert.equal(STATUS_TEXT.running, "处理中");
  assert.equal(STATUS_TEXT.done, "完成");
  assert.equal(STATUS_TEXT.failed, "失败");
  assert.equal(STATUS_TEXT.cancelled, "已取消");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test web/tests/errors.test.mjs web/tests/joblist.test.mjs`  
Expected: FAIL (modules missing)

- [ ] **Step 3: Write minimal implementation**

```js
// web/lib/errors.js
export class AppError extends Error {
  constructor(label, detail = "") {
    super(detail || label);
    this.label = label;
    this.detail = detail;
  }
}

export function friendlyError(e) {
  if (e instanceof AppError) {
    return e.detail ? `${e.label}：${e.detail}` : e.label;
  }
  if (e && typeof e === "object" && e.name === "AbortError") {
    return "已取消";
  }
  const msg = String((e && e.message) || e);
  if (msg.includes("已取消")) return "已取消";
  return `未知错误：${msg}`;
}
```

```js
// web/lib/download.js
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

export function baseName(pathLike) {
  const s = String(pathLike).replace(/\\/g, "/");
  const i = s.lastIndexOf("/");
  return i >= 0 ? s.slice(i + 1) : s;
}

export function stem(name) {
  const b = baseName(name);
  const i = b.lastIndexOf(".");
  return i > 0 ? b.slice(0, i) : b;
}
```

```js
// web/lib/joblist.js
export const STATUS_TEXT = {
  pending: "等待",
  running: "处理中",
  done: "完成",
  failed: "失败",
  cancelled: "已取消",
};

export function createJobList(container, { onCancel } = {}) {
  container.innerHTML = `
    <div class="row">
      <button type="button" class="btn secondary" data-act="cancel" disabled>取消</button>
    </div>
    <div class="progress"><i style="width:0%"></i></div>
    <table class="jobs">
      <thead><tr><th>文件</th><th>状态</th></tr></thead>
      <tbody></tbody>
    </table>
  `;
  const tbody = container.querySelector("tbody");
  const bar = container.querySelector(".progress > i");
  const cancelBtn = container.querySelector('[data-act="cancel"]');
  let cancelled = false;
  const rows = new Map();

  cancelBtn.addEventListener("click", () => {
    cancelled = true;
    if (onCancel) onCancel();
  });

  function renderStatus(id, status, detail = "") {
    const tr = rows.get(id);
    if (!tr) return;
    const td = tr.querySelector("td:last-child");
    td.className = `st-${status}`;
    td.textContent = STATUS_TEXT[status] || status;
    if (detail && (status === "failed" || status === "cancelled")) {
      td.textContent = status === "failed" ? `${STATUS_TEXT.failed}（${detail}）` : detail;
    }
  }

  return {
    get cancelled() {
      return cancelled;
    },
    reset() {
      cancelled = false;
      tbody.innerHTML = "";
      rows.clear();
      bar.style.width = "0%";
      cancelBtn.disabled = true;
    },
    submit(jobs) {
      this.reset();
      cancelBtn.disabled = false;
      for (const job of jobs) {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td></td><td class="st-pending"></td>`;
        tr.cells[0].textContent = job.name;
        tbody.appendChild(tr);
        rows.set(job.id, tr);
        renderStatus(job.id, "pending");
      }
    },
    setProgress(pct) {
      const v = Math.max(0, Math.min(100, pct | 0));
      bar.style.width = `${v}%`;
    },
    setStatus(id, status, detail) {
      renderStatus(id, status, detail);
    },
    finish() {
      cancelBtn.disabled = true;
    },
  };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test web/tests/errors.test.mjs web/tests/joblist.test.mjs`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/lib/errors.js web/lib/download.js web/lib/joblist.js web/tests/errors.test.mjs web/tests/joblist.test.mjs
git commit -m "feat(web): errors, download, job list helpers"
```

---

### Task 3: Image convert + crop + watermarks (`image_ops` / `annotate`)

**Files:**
- Create: `web/lib/image_ops.js`
- Create: `web/lib/annotate.js`
- Create: `web/tests/image_ops.test.mjs`
- Create: `web/tests/annotate.test.mjs`

**Interfaces:**
- Consumes: `AppError` from `errors.js`
- Produces:
  - `IMAGE_EXTS`, `OUT_FORMATS = { png, jpg, webp, bmp, gif }`
  - `async convertImage(file, { format, maxWidth, quality }) -> { blob, filename }`
  - `cropBoxValid(box, w, h) -> boolean` with box `[l,t,r,b]`
  - `cropCanvas(canvas, box) -> canvas`
  - `pastePos(cw, ch, mw, mh, position, margin) -> [x,y]`
  - `POSITIONS` = same five strings as desktop

- [ ] **Step 1: Write the failing tests**

```js
// web/tests/image_ops.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { OUT_EXTS, outputExtFor, qualityExts } from "../lib/image_ops.js";

test("output ext mapping", () => {
  assert.equal(outputExtFor("PNG"), ".png");
  assert.equal(outputExtFor("JPG"), ".jpg");
  assert.ok(OUT_EXTS.includes(".webp"));
});

test("quality only for lossy", () => {
  assert.ok(qualityExts().has(".jpg"));
  assert.ok(qualityExts().has(".webp"));
  assert.ok(!qualityExts().has(".png"));
});
```

```js
// web/tests/annotate.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { cropBoxValid, pastePos, POSITIONS } from "../lib/annotate.js";

test("crop validation matches desktop bounds rule", () => {
  assert.equal(cropBoxValid([0, 0, 32, 24], 64, 48), true);
  assert.equal(cropBoxValid([0, 0, 999, 999], 64, 48), false);
  assert.equal(cropBoxValid([10, 10, 10, 20], 64, 48), false);
});

test("paste position bottom_right", () => {
  const [x, y] = pastePos(100, 80, 10, 10, "bottom_right", 4);
  assert.equal(x, 100 - 10 - 4);
  assert.equal(y, 80 - 10 - 4);
});

test("paste position center", () => {
  assert.deepEqual(pastePos(100, 80, 10, 10, "center", 4), [45, 35]);
});

test("positions set same as desktop", () => {
  assert.deepEqual([...POSITIONS].sort(), [
    "bottom_left", "bottom_right", "center", "top_left", "top_right",
  ]);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test web/tests/image_ops.test.mjs web/tests/annotate.test.mjs`  
Expected: FAIL (modules missing)

- [ ] **Step 3: Write minimal implementation**

```js
// web/lib/image_ops.js
import { AppError } from "./errors.js";

export const IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"];
export const OUT_FORMATS = ["PNG", "JPG", "WebP", "BMP", "GIF"];

const MIME = {
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".bmp": "image/bmp",
  ".gif": "image/gif",
};

export function outputExtFor(fmt) {
  const f = String(fmt).toLowerCase();
  if (f === "jpg" || f === "jpeg") return ".jpg";
  if (f === "png") return ".png";
  if (f === "webp") return ".webp";
  if (f === "bmp") return ".bmp";
  if (f === "gif") return ".gif";
  throw new AppError("图片处理失败", `不支持的输出格式: ${fmt}`);
}

export function qualityExts() {
  return new Set([".jpg", ".jpeg", ".webp"]);
}

export async function loadImageBitmap(file) {
  try {
    return await createImageBitmap(file);
  } catch (e) {
    throw new AppError("图片处理失败", `无法读取图片: ${file.name || ""}（${e}）`);
  }
}

function drawScaled(bitmap, maxWidth) {
  let w = bitmap.width;
  let h = bitmap.height;
  if (maxWidth && maxWidth > 0 && w > maxWidth) {
    h = Math.max(1, Math.round(h * (maxWidth / w)));
    w = maxWidth;
  }
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(bitmap, 0, 0, w, h);
  return canvas;
}

export async function convertImage(file, { format, maxWidth = 0, quality = 90 } = {}) {
  const ext = outputExtFor(format || "PNG");
  const bitmap = await loadImageBitmap(file);
  // GIF animation is flattened to first frame (same as desktop convert of .gif source)
  const canvas = drawScaled(bitmap, maxWidth);
  bitmap.close && bitmap.close();
  const mime = MIME[ext];
  const q = Math.max(1, Math.min(100, quality));
  const opts = qualityExts().has(ext) ? { type: mime, quality: q / 100 } : { type: mime };
  const blob = await new Promise((resolve, reject) => {
    canvas.toBlob((b) => (b ? resolve(b) : reject(new AppError("图片处理失败", "保存失败"))), opts.type, opts.quality);
  });
  const outName = (file.name || "image").replace(/\.[^.]+$/, "") + ext;
  return { blob, filename: outName, width: canvas.width, height: canvas.height };
}
```

```js
// web/lib/annotate.js
import { AppError } from "./errors.js";

export const POSITIONS = [
  "top_left",
  "top_right",
  "bottom_left",
  "bottom_right",
  "center",
];

export function cropBoxValid(box, w, h) {
  const [l, t, r, b] = box;
  return Number.isFinite(l) && Number.isFinite(t) && Number.isFinite(r) && Number.isFinite(b)
    && 0 <= l && l < r && r <= w && 0 <= t && t < b && b <= h;
}

export function cropCanvas(src, box) {
  const [l, t, r, b] = box;
  if (!cropBoxValid(box, src.width, src.height)) {
    throw new AppError("图片处理失败", `裁剪区域无效: 必须在 0..${src.width} × 0..${src.height} 范围内`);
  }
  const out = document.createElement("canvas");
  out.width = r - l;
  out.height = b - t;
  out.getContext("2d").drawImage(src, l, t, r - l, b - t, 0, 0, out.width, out.height);
  return out;
}

export function pastePos(cw, ch, mw, mh, position, margin = 16) {
  if (!POSITIONS.includes(position)) {
    throw new AppError("图片处理失败", `未知水印位置: ${position}`);
  }
  if (position === "top_left") return [margin, margin];
  if (position === "top_right") return [cw - mw - margin, margin];
  if (position === "bottom_left") return [margin, ch - mh - margin];
  if (position === "bottom_right") return [cw - mw - margin, ch - mh - margin];
  return [(cw - mw) >> 1, (ch - mh) >> 1];
}

export async function addTextWatermark(file, { text, fontSize = 32, color = "rgba(255,255,255,0.7)", position = "bottom_right", margin = 16 } = {}) {
  if (!text) throw new AppError("图片处理失败", "水印文字不能为空");
  const bitmap = await createImageBitmap(file);
  const canvas = document.createElement("canvas");
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(bitmap, 0, 0);
  bitmap.close && bitmap.close();
  ctx.font = `${fontSize}px sans-serif`;
  ctx.fillStyle = color;
  const m = ctx.measureText(text);
  const tw = m.width;
  const th = fontSize * 1.2;
  const [x, y] = pastePos(canvas.width, canvas.height, tw, th, position, margin);
  ctx.fillText(text, x, y);
  const blob = await new Promise((res, rej) => canvas.toBlob((b) => (b ? res(b) : rej(new AppError("图片处理失败", "保存失败"))), "image/png"));
  return { blob, filename: (file.name || "image").replace(/\.[^.]+$/, "") + "_wm.png" };
}

export async function addImageWatermark(file, markFile, { scale = 0.2, position = "bottom_right", margin = 16, opacity = 0.8 } = {}) {
  if (!(scale >= 0.05 && scale <= 1)) throw new AppError("图片处理失败", "水印缩放比例需在 0.05–1.0 之间");
  if (!(opacity >= 0 && opacity <= 1)) throw new AppError("图片处理失败", "透明度需在 0–1 之间");
  const base = await createImageBitmap(file);
  const mark = await createImageBitmap(markFile);
  const canvas = document.createElement("canvas");
  canvas.width = base.width;
  canvas.height = base.height;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(base, 0, 0);
  const mw = Math.max(1, Math.round(base.width * scale));
  const mh = Math.max(1, Math.round(mark.height * (mw / mark.width)));
  const off = document.createElement("canvas");
  off.width = mw;
  off.height = mh;
  const octx = off.getContext("2d");
  octx.globalAlpha = opacity;
  octx.drawImage(mark, 0, 0, mw, mh);
  const [x, y] = pastePos(canvas.width, canvas.height, mw, mh, position, margin);
  ctx.drawImage(off, x, y);
  base.close && base.close();
  mark.close && mark.close();
  const blob = await new Promise((res, rej) => canvas.toBlob((b) => (b ? res(b) : rej(new AppError("图片处理失败", "保存失败"))), "image/png"));
  return { blob, filename: (file.name || "image").replace(/\.[^.]+$/, "") + "_wm.png" };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test web/tests/image_ops.test.mjs web/tests/annotate.test.mjs`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/lib/image_ops.js web/lib/annotate.js web/tests/image_ops.test.mjs web/tests/annotate.test.mjs
git commit -m "feat(web): image convert, crop, watermarks"
```

---

### Task 4: GIF ops (split / merge)

**Files:**
- Create: `web/lib/gif_ops.js`
- Create: `web/tests/gif_ops.test.mjs`

**Interfaces:**
- Consumes: `AppError`, CDN `gifuct` global; `downloadBlob`
- Produces:
  - `loadGifFrames(file) -> Promise<{ width, height, frames: HTMLCanvasElement[] }>`
  - `splitGif(file, { step, cancelToken }) -> Promise<{ files: { name, blob }[] }>`
  - `mergeGif(files, { durationMs, loop, reverse, cancelToken }) -> Promise<{ blob, filename }>`

- [ ] **Step 1: Write the failing test**

```js
// web/tests/gif_ops.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { stepIndexKept, mergeOrder } from "../lib/gif_ops.js";

test("split step keeps first frame at step>=1", () => {
  assert.deepEqual([0, 1, 2, 3].filter((i) => stepIndexKept(i, 2)), [0, 2]);
  assert.deepEqual([0, 1, 2].filter((i) => stepIndexKept(i, 1)), [0, 1, 2]);
});

test("merge reverse order", () => {
  assert.deepEqual(mergeOrder(["a", "b"], true), ["b", "a"]);
  assert.deepEqual(mergeOrder(["a", "b"], false), ["a", "b"]);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test web/tests/gif_ops.test.mjs`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```js
// web/lib/gif_ops.js
import { AppError } from "./errors.js";

export function stepIndexKept(index, step) {
  return index % Math.max(1, step | 0) === 0;
}

export function mergeOrder(list, reverse) {
  const arr = [...list];
  return reverse ? arr.reverse() : arr;
}

function throwIfCancelled(token) {
  if (token && token.cancelled) throw new AppError("GIF 处理失败", "已取消");
}

function loadScriptOnce(src, check) {
  if (check()) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload = () => resolve();
    s.onerror = () => reject(new AppError("GIF 处理失败", `无法加载依赖: ${src}`));
    document.head.appendChild(s);
  });
}

export async function ensureGifuct() {
  await loadScriptOnce(
    "https://cdn.jsdelivr.net/npm/gifuct-js@2.1.2/dist/gifuct-js.min.js",
    () => typeof globalThis.gifuct !== "undefined"
  );
  if (typeof globalThis.gifuct === "undefined") {
    throw new AppError("GIF 处理失败", "gifuct 加载失败");
  }
}

export async function loadGifFrames(file) {
  await ensureGifuct();
  const buf = await file.arrayBuffer();
  let parsed;
  try {
    parsed = globalThis.gifuct.parseGIF(buf);
  } catch (e) {
    throw new AppError("GIF 处理失败", `无法读取 GIF: ${file.name}（${e}）`);
  }
  const frames = [];
  let width = 0;
  let height = 0;
  for (const frame of parsed.frames) {
    throwIfCancelled();
    const patch = parsed.decompressFrame(frame, true);
    if (!patch || !patch.patch) continue;
    width = width || parsed.lsd.width;
    height = height || parsed.lsd.height;
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    const img = ctx.createImageData(width, height);
    img.data.set(patch.patch);
    ctx.putImageData(img, 0, 0);
    frames.push(canvas);
  }
  if (!frames.length) throw new AppError("GIF 处理失败", "GIF 中没有可导出的帧");
  return { width: width || frames[0].width, height: height || frames[0].height, frames };
}

export async function splitGif(file, { step = 1, token } = {}) {
  if (step < 1) throw new AppError("GIF 处理失败", "抽稀步长至少为 1");
  const { frames } = await loadGifFrames(file);
  const base = (file.name || "a.gif").replace(/\.gif$/i, "");
  const files = [];
  let kept = 0;
  for (let i = 0; i < frames.length; i++) {
    throwIfCancelled(token);
    if (!stepIndexKept(i, step)) continue;
    kept += 1;
    const blob = await new Promise((res, rej) =>
      frames[i].toBlob((b) => (b ? res(b) : rej(new AppError("GIF 处理失败", "保存失败"))), "image/png")
    );
    files.push({ name: `${base}/frame_${String(kept).padStart(4, "0")}.png`, blob });
  }
  if (!files.length) throw new AppError("GIF 处理失败", "GIF 中没有可导出的帧");
  return { files };
}

export async function mergeGif(files, { durationMs = 100, loop = 0, reverse = false, token } = {}) {
  if (!files.length) throw new AppError("GIF 处理失败", "没有可合并的图片");
  if (durationMs < 10) throw new AppError("GIF 处理失败", "帧间隔至少 10 毫秒");
  // Encode via browser: draw frames to canvas and use ffmpeg-free pure encoder is heavy;
  // MVP: animated WebP/GIF via ImageEncoder when available, else sequential PNG zip fallback is NOT acceptable.
  // Use gifenc-style minimal: reuse gifuct only decodes. For merge we encode with a tiny LZW GIF writer below.
  const ordered = mergeOrder(files, reverse);
  const canvases = [];
  for (const f of ordered) {
    throwIfCancelled(token);
    const bmp = await createImageBitmap(f);
    const c = document.createElement("canvas");
    c.width = bmp.width;
    c.height = bmp.height;
    c.getContext("2d").drawImage(bmp, 0, 0);
    bmp.close && bmp.close();
    canvases.push(c);
  }
  const blob = encodeAnimatedGif(canvases, { durationMs, loop });
  const first = ordered[0];
  const base = (first.name || "out").replace(/\.[^.]+$/, "");
  return { blob, filename: `${base}.gif` };
}

/** Minimal GIF89a animated writer (RGBA frames, global palette = median-cut simplified to 6x6x6 web-safe). */
export function encodeAnimatedGif(canvases, { durationMs = 100, loop = 0 } = {}) {
  if (!canvases.length) throw new AppError("GIF 处理失败", "没有可合并的图片");
  const w = canvases[0].width;
  const h = canvases[0].height;
  const framesData = canvases.map((c) => c.getContext("2d").getImageData(0, 0, w, h).data);
  const palette = buildPalette(framesData);
  const out = [];
  // Header
  pushStr(out, "GIF89a");
  pushU16(out, w);
  pushU16(out, h);
  out.push(0xf7, 0, 0); // GCT flag, 256 colors
  for (let i = 0; i < 256; i++) {
    const p = palette[i] || [0, 0, 0];
    out.push(p[0], p[1], p[2]);
  }
  // Netscape loop
  pushStr(out, "\x21\xff\x0bNETSCAPE2.0\x03\x01");
  pushU16(out, loop);
  out.push(0);
  const delay = Math.max(2, Math.round(durationMs / 10));
  for (const data of framesData) {
    // Graphic control
    pushStr(out, "\x21\xf9\x04");
    out.push(0, delay & 0xff, (delay >> 8) & 0xff, 0, 0);
    // Image descriptor
    out.push(0x2c);
    pushU16(out, 0);
    pushU16(out, 0);
    pushU16(out, w);
    pushU16(out, h);
    out.push(0);
    const indices = mapToPalette(data, palette);
    const minCodeSize = 8;
    out.push(minCodeSize);
    const lzw = lzwEncode(indices, minCodeSize);
    for (let i = 0; i < lzw.length; i += 255) {
      const chunk = lzw.slice(i, i + 255);
      out.push(chunk.length);
      for (const b of chunk) out.push(b);
    }
    out.push(0);
  }
  out.push(0x3b);
  return new Blob([new Uint8Array(out)], { type: "image/gif" });
}

function pushStr(arr, s) {
  for (let i = 0; i < s.length; i++) arr.push(s.charCodeAt(i));
}
function pushU16(arr, v) {
  arr.push(v & 0xff, (v >> 8) & 0xff);
}

function buildPalette(allFrames) {
  const counts = new Map();
  for (const data of allFrames) {
    for (let i = 0; i < data.length; i += 16) {
      const key = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2];
      counts.set(key, (counts.get(key) || 0) + 1);
    }
  }
  const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 256);
  const pal = sorted.map((k) => [(k[0] >> 16) & 255, (k[0] >> 8) & 255, k[0] & 255]);
  while (pal.length < 256) pal.push([0, 0, 0]);
  return pal;
}

function mapToPalette(data, palette) {
  // nearest among palette (256) — fine for wallpapers MVP
  const idx = new Uint8Array((data.length / 4) | 0);
  for (let p = 0, i = 0; i < data.length; i += 4, p++) {
    const r = data[i], g = data[i + 1], b = data[i + 2];
    let best = 0, bestD = Infinity;
    for (let k = 0; k < palette.length; k++) {
      const pr = palette[k][0] - r, pg = palette[k][1] - g, pb = palette[k][2] - b;
      const d = pr * pr + pg * pg + pb * pb;
      if (d < bestD) { bestD = d; best = k; }
    }
    idx[p] = best;
  }
  return idx;
}

function lzwEncode(indices, minCodeSize) {
  // Standard GIF LZW
  const clear = 1 << minCodeSize;
  const eoi = clear + 1;
  let codeSize = minCodeSize + 1;
  let dict = new Map();
  let next = eoi + 1;
  const out = [];
  let bitBuf = 0;
  let bitCnt = 0;
  const bytes = [];
  function emit(code) {
    bitBuf |= code << bitCnt;
    bitCnt += codeSize;
    while (bitCnt >= 8) {
      bytes.push(bitBuf & 0xff);
      bitBuf >>= 8;
      bitCnt -= 8;
    }
  }
  function resetDict() {
    dict = new Map();
    next = eoi + 1;
    codeSize = minCodeSize + 1;
  }
  emit(clear);
  if (indices.length === 0) {
    emit(eoi);
    if (bitCnt) bytes.push(bitBuf & 0xff);
    return bytes;
  }
  let prefix = indices[0];
  for (let i = 1; i < indices.length; i++) {
    const k = indices[i];
    const key = prefix * 4096 + k;
    if (dict.has(key)) {
      prefix = dict.get(key);
      continue;
    }
    emit(prefix);
    dict.set(key, next);
    next++;
    if (next > (1 << codeSize)) {
      if (codeSize < 12) codeSize++;
      else {
        emit(clear);
        resetDict();
      }
    }
    prefix = k;
  }
  emit(prefix);
  emit(eoi);
  if (bitCnt) bytes.push(bitBuf & 0xff);
  // pack into sub-blocks handled by caller — return raw bytes; caller wraps in 255 chunks
  // Actually caller expects chunkable stream: return bytes array as-is
  return bytes;
}
```

Note to implementer: if LZW edge cases fail on real GIFs, replace `encodeAnimatedGif` internals with a known-good tiny encoder (e.g. vendored `gifenc` UMD from jsDelivr **pinned**) while keeping `mergeGif` signature. Prefer shipping pinned `gifenc@1.0.3` over a buggy hand-rolled LZW — **do that if any merge test with >2 frames or large frames fails**.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test web/tests/gif_ops.test.mjs`  
Expected: PASS

- [ ] **Step 5: Manual merge smoke**

Open image/gif page (after Task 8) or a scratch HTML that imports `mergeGif` with 2 tiny PNG blobs; confirm a `.gif` downloads and opens.

- [ ] **Step 6: Commit**

```bash
git add web/lib/gif_ops.js web/tests/gif_ops.test.mjs
git commit -m "feat(web): gif split and merge"
```

---

### Task 5: WE unpack JS ports (pkg / tex / mpkg)

**Files:**
- Create: `web/lib/we_pkg.js`
- Create: `web/lib/we_tex.js`
- Create: `web/lib/we_mpkg.js`
- Create: `web/tests/we_pkg.test.mjs`
- Create: `web/tests/we_tex.test.mjs`
- Create: `web/tests/we_mpkg.test.mjs`

**Interfaces:**
- Consumes: `AppError` — map desktop labels: `PKG 解包失败`, `TEX 解析失败`, `MPKG 解包失败`
- Produces:
  - `readPkgIndex(data: Uint8Array) -> { magic, entries: {name,offset,length}[] }`
  - `extractPkg(data) -> { files: {name, blob}[] }`
  - `extractEmbedded(texData) -> { ext, payload } | { ext: null, payload: null }`
  - `extractTex(texData, baseName) -> { name, blob }`
  - `extractMpkg(data) -> { files: {name, blob}[] }`
  - `detectKind(filename) -> "pkg"|"tex"|"mpkg"|null`

- [ ] **Step 1: Write failing tests (byte-identical fixtures to desktop)**

```js
// web/tests/we_pkg.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { readPkgIndex, extractPkg } from "../lib/we_pkg.js";

function buildPkg(files, magic = "PKGV0005") {
  const enc = new TextEncoder();
  const names = Object.keys(files);
  const header = enc.encode(magic);
  const blobs = names.map((n) => files[n]);
  const pre = 4 + header.length + 4 + names.reduce((s, n) => s + 4 + enc.encode(n).length + 8, 0);
  const parts = [];
  const pushU32 = (v) => {
    const b = new Uint8Array(4);
    new DataView(b.buffer).setUint32(0, v, true);
    parts.push(b);
  };
  pushU32(header.length);
  parts.push(header);
  pushU32(names.length);
  let off = 0;
  names.forEach((n, i) => {
    const nb = enc.encode(n);
    pushU32(nb.length);
    parts.push(nb);
    pushU32(off);
    pushU32(blobs[i].length);
    off += blobs[i].length;
  });
  const indexLen = parts.reduce((s, p) => s + p.length, 0);
  assert.equal(indexLen, pre);
  parts.push(...blobs);
  const total = parts.reduce((s, p) => s + p.length, 0);
  const out = new Uint8Array(total);
  let p = 0;
  for (const part of parts) {
    out.set(part, p);
    p += part.length;
  }
  return out;
}

test("read index", () => {
  const pkg = buildPkg({ "a.txt": new TextEncoder().encode("hello") });
  const { magic, entries } = readPkgIndex(pkg);
  assert.ok(magic.startsWith("PKGV"));
  assert.equal(entries[0].name, "a.txt");
  assert.equal(entries[0].length, 5);
});

test("extract payload", () => {
  const pkg = buildPkg({ "a.txt": new TextEncoder().encode("hello") });
  const { files } = extractPkg(pkg);
  assert.equal(new TextDecoder().decode(files[0].blob), "hello");
  assert.equal(files[0].name, "a.txt");
});
```

```js
// web/tests/we_tex.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { extractEmbedded } from "../lib/we_tex.js";

test("embedded png with length prefix", () => {
  const png = new Uint8Array([...new TextEncoder().encode("\x89PNG\r\n\x1a\n"), ...new Uint8Array(10)]);
  // build: 16 zeros + u32le(len) + png
  const len = new Uint8Array(4);
  new DataView(len.buffer).setUint32(0, png.length, true);
  const blob = new Uint8Array(16 + 4 + png.length + 8);
  blob.set(len, 16);
  blob.set(png, 20);
  const { ext } = extractEmbedded(blob);
  assert.equal(ext, ".png");
});

test("embedded mp4 ftyp", () => {
  const ftyp = new Uint8Array(20);
  const dv = new DataView(ftyp.buffer);
  dv.setUint32(0, 20, false);
  ftyp.set(new TextEncoder().encode("ftyp"), 4);
  ftyp.set(new TextEncoder().encode("isom"), 8);
  const blob = new Uint8Array(32 + 20 + 16);
  blob.set(ftyp, 32);
  const { ext } = extractEmbedded(blob);
  assert.equal(ext, ".mp4");
});
```

```js
// web/tests/we_mpkg.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { isMpkg, extractMpkg } from "../lib/we_mpkg.js";

test("isMpkg magic", () => {
  assert.equal(isMpkg(new TextEncoder().encode("PKGM0014xxxxxxxx")), true);
  assert.equal(isMpkg(new TextEncoder().encode("XXXX")), false);
});

test("carve mp4 from garbage-with-ftyp", () => {
  const ftyp = new Uint8Array(32);
  const dv = new DataView(ftyp.buffer);
  dv.setUint32(0, 32, false);
  ftyp.set(new TextEncoder().encode("ftyp"), 4);
  ftyp.set(new TextEncoder().encode("mp42"), 8);
  const moov = new Uint8Array(16);
  new DataView(moov.buffer).setUint32(0, 16, false);
  moov.set(new TextEncoder().encode("moov"), 4);
  const data = new Uint8Array(8 + 32 + 16 + 8);
  data.set(new TextEncoder().encode("PKGM0014"), 0);
  data.set(ftyp, 8);
  data.set(moov, 40);
  const { files } = extractMpkg(data);
  assert.ok(files.length >= 1);
  assert.ok(files.some((f) => f.name.endsWith(".mp4")));
});

test("garbage raises Chinese", () => {
  const data = new Uint8Array(116);
  data.set(new TextEncoder().encode("PKGM0019"), 0);
  data.fill(0x11, 8);
  assert.throws(() => extractMpkg(data), /MPKG|无法/);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test web/tests/we_pkg.test.mjs web/tests/we_tex.test.mjs web/tests/we_mpkg.test.mjs`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementations (port desktop logic)**

```js
// web/lib/we_pkg.js
import { AppError } from "./errors.js";

const label = "PKG 解包失败";

function readU32(data, pos) {
  if (pos + 4 > data.length) throw new AppError(label, "PKG 文件损坏：读取长度字段失败");
  return (data[pos] | (data[pos + 1] << 8) | (data[pos + 2] << 16) | (data[pos + 3] << 24)) >>> 0, pos + 4;
}

export function readPkgIndex(data) {
  if (data.length < 8) throw new AppError(label, "PKG 文件过小");
  let [headerLen, pos] = readU32(data, 0);
  if (headerLen > data.length - 4) throw new AppError(label, "不是有效的 Wallpaper Engine 包（头部长度异常）");
  const headerBytes = data.subarray(pos, pos + headerLen);
  pos += headerLen;
  const magic = new TextDecoder("utf-8", { fatal: false }).decode(headerBytes).replace(/\0+$/, "");
  if (headerLen && !/^(PKG|PKGM)/i.test(magic) && headerLen > 1024) {
    throw new AppError(label, `不是有效的 Wallpaper Engine 包（头部: ${magic.slice(0, 40)}）`);
  }
  let [count, pos2] = readU32(data, pos);
  pos = pos2;
  if (count > 1_000_000) throw new AppError(label, "不是有效的 Wallpaper Engine 包（文件数异常）");
  const entries = [];
  const td = new TextDecoder("utf-8", { fatal: false });
  for (let i = 0; i < count; i++) {
    let nameLen;
    [nameLen, pos] = readU32(data, pos);
    if (nameLen > 4096 || pos + nameLen + 8 > data.length) throw new AppError(label, "PKG 索引损坏");
    let name = td.decode(data.subarray(pos, pos + nameLen)).replace(/\0+$/, "").replace(/\\/g, "/");
    pos += nameLen;
    let offset, length;
    [offset, pos] = readU32(data, pos);
    [length, pos] = readU32(data, pos);
    entries.push({ name, offset, length });
  }
  return { magic, entries, indexEnd: pos };
}

function indexEnd(data) {
  let [headerLen, pos] = readU32(data, 0);
  pos += headerLen;
  let count;
  [count, pos] = readU32(data, pos);
  for (let i = 0; i < count; i++) {
    let nameLen;
    [nameLen, pos] = readU32(data, pos);
    pos += nameLen + 8;
  }
  return pos;
}

export function extractPkg(data) {
  const { entries } = readPkgIndex(data);
  const dataStart = indexEnd(data);
  const files = [];
  for (const entry of entries) {
    let start = dataStart + entry.offset;
    let end = start + entry.length;
    if (entry.length < 0 || start < 0 || end > data.length) {
      start = entry.offset;
      end = entry.offset + entry.length;
      if (end > data.length || start < 0) throw new AppError(label, `条目越界: ${entry.name}`);
    }
    const name = entry.name.replace(/^\/+/, "");
    if (name.split("/").some((seg) => seg === "..")) {
      throw new AppError(label, `非法路径: ${entry.name}`);
    }
    files.push({ name, blob: data.slice(start, end) });
  }
  return { files };
}
```

```js
// web/lib/we_tex.js
import { AppError } from "./errors.js";

const label = "TEX 解析失败";
const PNG_SIG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

function findSub(hay, needle, from = 0) {
  // needle: number[] 
  outer: for (let i = from; i <= hay.length - needle.length; i++) {
    for (let j = 0; j < needle.length; j++) if (hay[i + j] !== needle[j]) continue outer;
    return i;
  }
  return -1;
}

function u32le(data, i) {
  return (data[i] | (data[i + 1] << 8) | (data[i + 2] << 16) | (data[i + 3] << 24)) >>> 0;
}

function u32be(data, i) {
  return ((data[i] << 24) | (data[i + 1] << 16) | (data[i + 2] << 8) | data[i + 3]) >>> 0;
}

export function extractEmbedded(texData) {
  const candidates = [];
  // PNG
  let idx = 0;
  while (true) {
    const i = findSub(texData, PNG_SIG, idx);
    if (i < 0) break;
    let end = texData.length;
    if (i >= 4) {
      const ln = u32le(texData, i - 4);
      if (ln >= 8 && i + ln <= texData.length) end = i + ln;
    }
    candidates.push({ ext: ".png", start: i, end });
    idx = i + 1;
  }
  // JPEG SOI
  const j = findSub(texData, [0xff, 0xd8, 0xff]);
  if (j >= 0) {
    let end = texData.length;
    if (j >= 4) {
      const ln = u32le(texData, j - 4);
      if (ln >= 16 && j + ln <= texData.length) end = j + ln;
    }
    const eoi = findSub(texData, [0xff, 0xd9], j);
    if (eoi !== -1 && eoi + 2 <= end) end = eoi + 2;
    candidates.push({ ext: ".jpg", start: j, end });
  }
  // WebP
  idx = 0;
  while (true) {
    const i = findSub(texData, [0x57, 0x45, 0x42, 0x50], idx); // WEBP
    if (i < 0) break;
    if (i >= 4 && texData[i - 8] === 0x52 && texData[i - 7] === 0x49 && texData[i - 6] === 0x46 && texData[i - 5] === 0x46) {
      const riff = i - 8;
      const size = u32le(texData, riff + 4) + 8;
      if (riff + size <= texData.length) candidates.push({ ext: ".webp", start: riff, end: riff + size });
    }
    idx = i + 1;
  }
  // MP4
  const ftyp = [0x66, 0x74, 0x79, 0x70];
  idx = 0;
  while (true) {
    const i = findSub(texData, ftyp, idx);
    if (i < 0) break;
    if (i >= 4) {
      const boxSize = u32be(texData, i - 4);
      const start = i - 4;
      if (boxSize >= 8 && boxSize <= texData.length - start) {
        candidates.push({ ext: ".mp4", start, end: start + boxSize });
      } else {
        candidates.push({ ext: ".mp4", start, end: texData.length });
      }
    }
    idx = i + 1;
  }
  if (!candidates.length) return { ext: null, payload: null };
  const priority = { ".mp4": 0, ".png": 1, ".webp": 2, ".jpg": 3 };
  candidates.sort((a, b) => (priority[a.ext] ?? 9) - (priority[b.ext] ?? 9) || (b.end - b.start) - (a.end - a.start));
  const c = candidates[0];
  const payload = texData.slice(c.start, c.end);
  if (payload.length < 16) return { ext: null, payload: null };
  return { ext: c.ext, payload };
}

export function extractTex(texData, baseName) {
  const { ext, payload } = extractEmbedded(texData);
  if (ext && payload) {
    return { name: `${baseName}${ext}`, blob: payload };
  }
  return { name: `${baseName}.tex`, blob: texData };
}
```

```js
// web/lib/we_mpkg.js
import { AppError } from "./errors.js";
import { extractPkg, readPkgIndex } from "./we_pkg.js";
import { extractEmbedded, extractTex } from "./we_tex.js";

const label = "MPKG 解包失败";
const MAGICS = ["PKGM0014", "PKGM0015", "PKGM0016", "PKGM0017", "PKGM0018", "PKGM0019"];

export function isMpkg(data) {
  const head = data.subarray(0, 64);
  const s = new TextDecoder("utf-8", { fatal: false }).decode(head);
  return MAGICS.some((m) => s.includes(m)) || s.startsWith("PKGM");
}

function findFtyp(data, from = 0) {
  const needle = [0x66, 0x74, 0x79, 0x70];
  for (let i = from; i <= data.length - 4; i++) {
    if (data[i] === needle[0] && data[i + 1] === needle[1] && data[i + 2] === needle[2] && data[i + 3] === needle[3]) return i;
  }
  return -1;
}

function u32be(data, i) {
  return ((data[i] << 24) | (data[i + 1] << 16) | (data[i + 2] << 8) | data[i + 3]) >>> 0;
}

function extractMp4Blobs(data) {
  const out = [];
  let idx = 0;
  while (true) {
    const i = findFtyp(data, idx);
    if (i < 0) break;
    if (i >= 4) {
      const size = u32be(data, i - 4);
      const start = i - 4;
      if (size >= 8 && start + size <= data.length) {
        out.push(data.slice(start, start + size));
      } else if (start >= 0) {
        out.push(data.slice(start, Math.min(data.length, i + 4096)));
      }
    }
    idx = i + 4;
  }
  // dedup by containment
  out.sort((a, b) => b.length - a.length);
  const kept = [];
  for (const b of out) {
    if (kept.some((k) => includesBytes(k, b))) continue;
    kept.push(b);
  }
  return kept;
}

function includesBytes(hay, needle) {
  if (needle.length > hay.length) return false;
  outer: for (let i = 0; i <= hay.length - needle.length; i += Math.max(1, needle.length >> 8)) {
    for (let j = 0; j < needle.length; j++) if (hay[i + j] !== needle[j]) continue outer;
    return true;
  }
  return false;
}

function carveMedia(data) {
  const results = [];
  for (const blob of extractMp4Blobs(data)) results.push({ ext: ".mp4", blob });
  const img = extractEmbedded(data);
  if (img.ext && img.ext !== ".mp4" && img.payload) results.push({ ext: img.ext, blob: img.payload });
  // standalone PNG
  const sig = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  let idx = 0;
  while (true) {
    let i = -1;
    for (let p = idx; p <= data.length - 8; p++) {
      if (sig.every((b, k) => data[p + k] === b)) { i = p; break; }
    }
    if (i < 0) break;
    let iend = -1;
    for (let p = i; p <= data.length - 4; p++) {
      if (data[p] === 0x49 && data[p + 1] === 0x45 && data[p + 2] === 0x4e && data[p + 3] === 0x44) { iend = p; break; }
    }
    const end = iend !== -1 ? iend + 8 : Math.min(data.length, i + 64 * 1024);
    if (end <= data.length) results.push({ ext: ".png", blob: data.slice(i, end) });
    idx = i + 1;
    if (results.length > 64) break;
  }
  return results;
}

export function extractMpkg(data) {
  if (data.length < 16) throw new AppError(label, "MPKG 文件过小");
  try {
    const { entries } = readPkgIndex(data);
    if (entries && entries.length < 500_000) {
      try {
        const { files } = extractPkg(data);
        const out = files.map((f) =>
          f.name.toLowerCase().endsWith(".tex")
            ? extractTex(f.blob, f.name.replace(/\.tex$/i, ""))
            : f
        );
        if (out.length) return { files: out };
      } catch {
        /* fall through */
      }
    }
  } catch {
    /* fall through */
  }
  const carved = carveMedia(data);
  if (!carved.length) {
    throw new AppError(label, "无法从 MPKG 中提取内容：未知加密或版本，请确认是 Wallpaper Engine 导出的 .mpkg");
  }
  return {
    files: carved.map((c, i) => ({
      name: `extracted_${String(i + 1).padStart(2, "0")}${c.ext}`,
      blob: c.blob,
    })),
  };
}
```

Also add:

```js
// web/lib/we_pkg.js or small we_detect.js — put in we_mpkg.js exports
export function detectKind(filename) {
  const n = String(filename).toLowerCase();
  if (n.endsWith(".pkg")) return "pkg";
  if (n.endsWith(".tex")) return "tex";
  if (n.endsWith(".mpkg")) return "mpkg";
  return null;
}
```

(Move `detectKind` to `web/lib/we_detect.js` if cleaner — one export file is fine.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test web/tests/we_pkg.test.mjs web/tests/we_tex.test.mjs web/tests/we_mpkg.test.mjs`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/lib/we_pkg.js web/lib/we_tex.js web/lib/we_mpkg.js web/lib/we_detect.js web/tests/we_pkg.test.mjs web/tests/we_tex.test.mjs web/tests/we_mpkg.test.mjs
git commit -m "feat(web): WE pkg/tex/mpkg unpack ports"
```

---

### Task 6: Image page UI

**Files:**
- Create: `web/pages/image.js`
- Modify: `web/app.js` (register `#/image` — already lazy-loaded in Task 1)

**Interfaces:**
- Consumes: `convertImage`, `cropCanvas`, `addTextWatermark`, `addImageWatermark`, `createJobList`, `downloadBlob`, `stem`, JSZip CDN
- Produces: `mountImage(root)`

- [ ] **Step 1: Implement page**

```js
// web/pages/image.js
import { OUT_FORMATS, convertImage } from "../lib/image_ops.js";
import { addImageWatermark, addTextWatermark, cropCanvas } from "../lib/annotate.js";
import { createJobList } from "../lib/joblist.js";
import { downloadBlob, stem } from "../lib/download.js";
import { friendlyError, AppError } from "../lib/errors.js";

export function mountImage(root) {
  root.innerHTML = `
    <div class="row">
      <label>文件 <input type="file" id="files" multiple accept="image/*" /></label>
      <label>格式
        <select id="fmt">${OUT_FORMATS.map((f) => `<option${f === "JPG" ? " selected" : ""}>${f}</option>`).join("")}</select>
      </label>
      <label>质量 <input type="range" id="q" min="1" max="100" value="90" /><span id="qv">90</span></label>
      <label><input type="checkbox" id="scale" /> 缩放到宽度</label>
      <input type="number" id="sw" value="1920" min="16" max="8192" disabled style="width:90px" />
      <button type="button" class="btn" id="start">开始转换</button>
      <button type="button" class="btn secondary" id="zip">打包下载 ZIP</button>
    </div>
    <div class="row">
      <button type="button" class="btn secondary" id="crop">裁剪第一张…</button>
      <button type="button" class="btn secondary" id="wmtext">文字水印…</button>
      <button type="button" class="btn secondary" id="wmimg">图片水印…</button>
      <input type="file" id="markfile" accept="image/*" hidden />
    </div>
    <div id="jobs"></div>
    <pre class="err" id="err"></pre>
  `;
  const jobs = createJobList(root.querySelector("#jobs"));
  const err = root.querySelector("#err");
  const $ = (id) => root.querySelector(`#${id}`);
  const outputs = [];

  $("q").addEventListener("input", () => ($("qv").textContent = $("q").value));
  $("scale").addEventListener("change", () => {
    $("sw").disabled = !$("scale").checked;
  });

  async function runOne(file, opts, jobName) {
    if (jobs.cancelled) throw new AppError("图片处理失败", "已取消");
    const { blob, filename } = await convertImage(file, opts);
    outputs.push({ blob, filename });
    return filename;
  }

  $("start").addEventListener("click", async () => {
    err.textContent = "";
    const files = [...$("files").files];
    if (!files.length) {
      err.textContent = "请先选择图片文件";
      return;
    }
    const fmt = $("fmt").value;
    const quality = Number($("q").value);
    const maxWidth = $("scale").checked ? Number($("sw").value) : 0;
    jobs.submit(files.map((f, i) => ({ id: i, name: f.name })));
    for (let i = 0; i < files.length; i++) {
      jobs.setStatus(i, "running");
      try {
        await runOne(files[i], { format: fmt, quality, maxWidth });
        jobs.setStatus(i, "done");
      } catch (e) {
        const msg = friendlyError(e);
        jobs.setStatus(i, msg === "已取消" ? "cancelled" : "failed", msg);
        if (msg === "已取消") break;
      }
    }
    jobs.finish();
  });

  $("zip").addEventListener("click", async () => {
    if (!outputs.length) {
      err.textContent = "还没有可下载的输出";
      return;
    }
    await ensureJszip();
    const zip = new globalThis.JSZip();
    for (const o of outputs) zip.file(o.filename, o.blob);
    const blob = await zip.generateAsync({ type: "blob" });
    downloadBlob(blob, "images.zip");
  });

  async function firstBitmap() {
    const f = $("files").files[0];
    if (!f) throw new AppError("图片处理失败", "请先添加图片文件");
    return { file: f, bitmap: await createImageBitmap(f) };
  }

  $("crop").addEventListener("click", async () => {
    err.textContent = "";
    try {
      const { file, bitmap } = await firstBitmap();
      const box = await pickBoxOnPage(bitmap);
      if (!box) return;
      const canvas = cropCanvas(bitmap, box);
      const blob = await new Promise((res, rej) =>
        canvas.toBlob((b) => (b ? res(b) : rej(new AppError("图片处理失败", "保存失败"))), "image/png")
      );
      const filename = `${stem(file.name)}_crop.png`;
      outputs.push({ blob, filename });
      downloadBlob(blob, filename);
      bitmap.close && bitmap.close();
    } catch (e) {
      err.textContent = friendlyError(e);
    }
  });

  $("wmtext").addEventListener("click", async () => {
    err.textContent = "";
    try {
      const { file, bitmap } = await firstBitmap();
      bitmap.close && bitmap.close();
      const text = prompt("水印文字", "我的壁纸");
      if (!text) return;
      const pos = prompt("位置 top_left|top_right|bottom_left|bottom_right|center", "bottom_right") || "bottom_right";
      const { blob, filename } = await addTextWatermark(file, { text, position: pos });
      outputs.push({ blob, filename });
      downloadBlob(blob, filename);
    } catch (e) {
      err.textContent = friendlyError(e);
    }
  });

  $("wmimg").addEventListener("click", async () => {
    err.textContent = "";
    try {
      const { file } = await firstBitmap();
      $("markfile").click();
      $("markfile").onchange = async () => {
        const mark = $("markfile").files[0];
        if (!mark) return;
        const { blob, filename } = await addImageWatermark(file, mark, { scale: 0.2, opacity: 0.8, position: "bottom_right" });
        outputs.push({ blob, filename });
        downloadBlob(blob, filename);
      };
    } catch (e) {
      err.textContent = friendlyError(e);
    }
  });
}

async function ensureJszip() {
  if (globalThis.JSZip) return;
  await new Promise((res, rej) => {
    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js";
    s.onload = res;
    s.onerror = () => rej(new AppError("图片处理失败", "JSZip 加载失败"));
    document.head.appendChild(s);
  });
}

function pickBoxOnPage(bitmap) {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:50;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:8px";
    const canvas = document.createElement("canvas");
    const maxW = Math.min(window.innerWidth - 40, bitmap.width);
    const scale = Math.min(1, maxW / bitmap.width);
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    canvas.style.maxWidth = "90vw";
    canvas.style.maxHeight = "80vh";
    canvas.style.cursor = "crosshair";
    const ctx = canvas.getContext("2d");
    ctx.drawImage(bitmap, 0, 0);
    const hint = document.createElement("div");
    hint.textContent = "按住左键拖拽选择区域，松开后自动确认";
    hint.style.color = "#e6e9ef";
    const bar = document.createElement("div");
    const cancel = document.createElement("button");
    cancel.className = "btn secondary";
    cancel.textContent = "取消";
    cancel.onclick = () => {
      overlay.remove();
      resolve(null);
    };
    bar.appendChild(cancel);
    overlay.append(canvas, hint, bar);
    document.body.appendChild(overlay);
    let start = null;
    let snapshot = null;
    canvas.onmousedown = (ev) => {
      const r = canvas.getBoundingClientRect();
      const x = ((ev.clientX - r.left) / r.width) * bitmap.width;
      const y = ((ev.clientY - r.top) / r.height) * bitmap.height;
      start = [x, y];
      snapshot = ctx.getImageData(0, 0, canvas.width, canvas.height);
    };
    canvas.onmousemove = (ev) => {
      if (!start) return;
      const r = canvas.getBoundingClientRect();
      const x = ((ev.clientX - r.left) / r.width) * bitmap.width;
      const y = ((ev.clientY - r.top) / r.height) * bitmap.height;
      ctx.putImageData(snapshot, 0, 0);
      ctx.strokeStyle = "#3b82f6";
      ctx.fillStyle = "rgba(59,130,246,0.25)";
      const l = Math.min(start[0], x);
      const t = Math.min(start[1], y);
      const w = Math.abs(x - start[0]);
      const h = Math.abs(y - start[1]);
      ctx.fillRect(l, t, w, h);
      ctx.strokeRect(l, t, w, h);
    };
    canvas.onmouseup = (ev) => {
      if (!start) return;
      const r = canvas.getBoundingClientRect();
      const x = ((ev.clientX - r.left) / r.width) * bitmap.width;
      const y = ((ev.clientY - r.top) / r.height) * bitmap.height;
      const box = [
        Math.round(Math.min(start[0], x)),
        Math.round(Math.min(start[1], y)),
        Math.round(Math.max(start[0], x)),
        Math.round(Math.max(start[1], y)),
      ];
      overlay.remove();
      if (box[2] - box[0] < 2 || box[3] - box[1] < 2) resolve(null);
      else resolve(box);
    };
  });
}
```

- [ ] **Step 2: Manual smoke**

Run: `python -m http.server 8765 -d web` → `#/image`  
Expected: convert 1 JPG, crop once, text watermark once; statuses update.

- [ ] **Step 3: Commit**

```bash
git add web/pages/image.js
git commit -m "feat(web): image page UI"
```

---

### Task 7: GIF page UI

**Files:**
- Create: `web/pages/gif.js`
- Modify: `web/app.js` if needed (lazy route already present)

**Interfaces:**
- Consumes: `splitGif`, `mergeGif`, `createJobList`, `downloadBlob`, `ensureJszip`
- Produces: `mountGif(root)`

- [ ] **Step 1: Implement page**

```js
// web/pages/gif.js
import { mergeGif, splitGif } from "../lib/gif_ops.js";
import { createJobList } from "../lib/joblist.js";
import { downloadBlob, stem } from "../lib/download.js";
import { friendlyError, AppError } from "../lib/errors.js";

export function mountGif(root) {
  root.innerHTML = `
    <div class="row">
      <label>模式
        <select id="mode">
          <option value="split">拆帧（GIF → PNG 序列）</option>
          <option value="merge">合帧（图片 → GIF）</option>
        </select>
      </label>
      <label id="wstep">抽稀步长 <input type="number" id="step" min="1" max="30" value="1" /></label>
      <label id="wdur" hidden>帧间隔(ms) <input type="number" id="dur" min="10" max="5000" value="100" /></label>
      <label id="wrev" hidden><input type="checkbox" id="rev" /> 倒放</label>
      <label id="wloop" hidden><input type="checkbox" id="loop" checked /> 无限循环</label>
      <label>文件 <input type="file" id="files" multiple accept="image/*,.gif" /></label>
      <button type="button" class="btn" id="start">开始</button>
      <button type="button" class="btn secondary" id="zip" hidden>打包下载 ZIP</button>
    </div>
    <div id="jobs"></div>
    <pre class="err" id="err"></pre>
  `;
  const $ = (id) => root.querySelector(`#${id}`);
  const jobs = createJobList(root.querySelector("#jobs"), {
    onCancel() {
      token.cancelled = true;
    },
  });
  const token = { cancelled: false };
  const outputs = [];
  let splitFiles = [];

  function syncMode() {
    const split = $("mode").value === "split";
    $("wstep").hidden = !split;
    $("wdur").hidden = split;
    $("wrev").hidden = split;
    $("wloop").hidden = split;
    $("zip").hidden = !split;
    $("start").textContent = split ? "开始拆帧" : "开始合帧";
    $("files").accept = split ? ".gif,image/gif" : "image/*,.gif";
  }
  $("mode").addEventListener("change", syncMode);
  syncMode();

  $("start").addEventListener("click", async () => {
    const err = $("err");
    err.textContent = "";
    token.cancelled = false;
    const files = [...$("files").files];
    if (!files.length) {
      err.textContent = $("mode").value === "split" ? "请先添加 GIF 文件" : "请先添加图片序列";
      return;
    }
    if ($("mode").value === "split") {
      jobs.submit(files.map((f, i) => ({ id: i, name: f.name })));
      splitFiles = [];
      for (let i = 0; i < files.length; i++) {
        if (jobs.cancelled) {
          jobs.setStatus(i, "cancelled", "已取消");
          continue;
        }
        jobs.setStatus(i, "running");
        try {
          const { files: parts } = await splitGif(files[i], {
            step: Number($("step").value),
            token,
          });
          splitFiles.push(...parts);
          jobs.setStatus(i, "done");
        } catch (e) {
          const msg = friendlyError(e);
          jobs.setStatus(i, msg === "已取消" ? "cancelled" : "failed", msg);
          if (msg === "已取消") continue;
        }
      }
      jobs.finish();
      return;
    }
    // merge
    const ordered = [...files].sort((a, b) => a.name.localeCompare(b.name));
    if (ordered.length < 1) {
      err.textContent = "请先添加图片序列（按文件名排序）";
      return;
    }
    jobs.submit([{ id: 0, name: ordered[0].name }]);
    jobs.setStatus(0, "running");
    try {
      const { blob, filename } = await mergeGif(ordered, {
        durationMs: Number($("dur").value),
        loop: $("loop").checked ? 0 : 1,
        reverse: $("rev").checked,
        token,
      });
      outputs.push({ blob, filename });
      jobs.setStatus(0, "done");
      downloadBlob(blob, filename);
    } catch (e) {
      const msg = friendlyError(e);
      jobs.setStatus(0, msg === "已取消" ? "cancelled" : "failed", msg);
    }
    jobs.finish();
  });

  $("zip").addEventListener("click", async () => {
    if (!splitFiles.length) {
      $("err").textContent = "还没有拆帧结果";
      return;
    }
    await ensureJszipGif();
    const zip = new globalThis.JSZip();
    for (const f of splitFiles) zip.file(f.name, f.blob);
    downloadBlob(await zip.generateAsync({ type: "blob" }), "frames.zip");
  });
}

async function ensureJszipGif() {
  if (globalThis.JSZip) return;
  await new Promise((res, rej) => {
    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js";
    s.onload = res;
    s.onerror = () => rej(new AppError("GIF 处理失败", "JSZip 加载失败"));
    document.head.appendChild(s);
  });
}
```

- [ ] **Step 2: Manual smoke** — split 2-frame GIF; merge 2 PNGs; cancel mid-split.

- [ ] **Step 3: Commit**

```bash
git add web/pages/gif.js
git commit -m "feat(web): gif page UI"
```

---

### Task 8: Unpack page UI

**Files:**
- Create: `web/pages/unpack.js`

**Interfaces:**
- Consumes: `extractPkg`, `extractTex`, `extractMpkg`, `detectKind`, `createJobList`, `downloadBlob`, JSZip
- Produces: `mountUnpack(root)`

- [ ] **Step 1: Implement page**

```js
// web/pages/unpack.js
import { extractMpkg } from "../lib/we_mpkg.js";
import { extractPkg } from "../lib/we_pkg.js";
import { extractTex } from "../lib/we_tex.js";
import { detectKind } from "../lib/we_detect.js";
import { createJobList } from "../lib/joblist.js";
import { downloadBlob, stem } from "../lib/download.js";
import { friendlyError } from "../lib/errors.js";

export function mountUnpack(root) {
  root.innerHTML = `
    <div class="row">
      <label>文件 <input type="file" id="files" multiple accept=".pkg,.tex,.mpkg" /></label>
      <button type="button" class="btn" id="start">开始解包</button>
      <button type="button" class="btn secondary" id="dl">打包下载 ZIP</button>
    </div>
    <div id="jobs"></div>
    <pre class="err" id="err"></pre>
  `;
  const $ = (id) => root.querySelector(`#${id}`);
  const jobs = createJobList(root.querySelector("#jobs"));
  let allFiles = [];

  $("start").addEventListener("click", async () => {
    $("err").textContent = "";
    const files = [...$("files").files];
    if (!files.length) {
      $("err").textContent = "请先添加 .pkg / .tex / .mpkg 文件";
      return;
    }
    jobs.submit(files.map((f, i) => ({ id: i, name: f.name })));
    allFiles = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      const kind = detectKind(f.name);
      if (!kind) {
        jobs.setStatus(i, "failed", "不支持的文件类型");
        continue;
      }
      jobs.setStatus(i, "running");
      try {
        const buf = new Uint8Array(await f.arrayBuffer());
        const base = stem(f.name);
        let result;
        if (kind === "pkg") result = extractPkg(buf);
        else if (kind === "tex") result = { files: [extractTex(buf, base)] };
        else result = extractMpkg(buf);
        for (const item of result.files) allFiles.push(item);
        jobs.setStatus(i, "done");
      } catch (e) {
        jobs.setStatus(i, "failed", friendlyError(e));
      }
    }
    jobs.finish();
  });

  $("dl").addEventListener("click", async () => {
    if (!allFiles.length) {
      $("err").textContent = "还没有解包结果";
      return;
    }
    await new Promise((res, rej) => {
      if (globalThis.JSZip) return res();
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js";
      s.onload = res;
      s.onerror = () => rej(new Error("JSZip 加载失败"));
      document.head.appendChild(s);
    });
    const zip = new globalThis.JSZip();
    for (const f of allFiles) zip.file(f.name, f.blob);
    downloadBlob(await zip.generateAsync({ type: "blob" }), "unpacked.zip");
  });
}
```

Also create `web/lib/we_detect.js` if not already in Task 5:

```js
export function detectKind(filename) {
  const n = String(filename).toLowerCase();
  if (n.endsWith(".pkg")) return "pkg";
  if (n.endsWith(".tex")) return "tex";
  if (n.endsWith(".mpkg")) return "mpkg";
  return null;
}
```

- [ ] **Step 2: Manual smoke** with fixture bytes generated from Task 5 builders or desktop-created sample.

- [ ] **Step 3: Commit**

```bash
git add web/pages/unpack.js web/lib/we_detect.js
git commit -m "feat(web): unpack page UI"
```

---

### Task 9: Video bridge + video page (ffmpeg.wasm)

**Files:**
- Create: `web/lib/video_bridge.js`
- Create: `web/lib/video_limits.js`
- Create: `web/pages/video.js`
- Create: `web/tests/video_limits.test.mjs`

**Interfaces:**
- Consumes: `AppError` label `视频处理失败`; job list; download
- Produces:
  - `MAX_VIDEO_BYTES`, `MAX_VIDEO_SECONDS`
  - `assertVideoLimits(file) -> void` (throws AppError)
  - `ensureFFmpeg(onLog) -> Promise<FFmpeg>`
  - `runFFmpeg(args, { onProgress, cancelToken }) -> Promise<void>`
  - `mountVideo(root)`

- [ ] **Step 1: Write the failing test**

```js
// web/tests/video_limits.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { assertVideoLimits, MAX_VIDEO_BYTES, MAX_VIDEO_SECONDS } from "../lib/video_limits.js";

test("limits constants", () => {
  assert.equal(MAX_VIDEO_BYTES, 100 * 1024 * 1024);
  assert.equal(MAX_VIDEO_SECONDS, 300);
});

test("assert rejects oversize", () => {
  assert.throws(() => assertVideoLimits({ name: "a.mp4", size: MAX_VIDEO_BYTES + 1 }), /桌面/);
  assert.throws(() => assertVideoLimits({ name: "a.mp4", size: 100, durationSec: MAX_VIDEO_SECONDS + 1 }), /桌面/);
  assert.doesNotThrow(() => assertVideoLimits({ name: "a.mp4", size: 100, durationSec: 1 }));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test web/tests/video_limits.test.mjs`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```js
// web/lib/video_limits.js
import { AppError } from "./errors.js";

export const MAX_VIDEO_BYTES = 100 * 1024 * 1024;
export const MAX_VIDEO_SECONDS = 300;

export function assertVideoLimits(fileLike) {
  const size = fileLike.size ?? 0;
  if (size > MAX_VIDEO_BYTES) {
    throw new AppError("视频处理失败", `单文件超过 ${Math.round(MAX_VIDEO_BYTES / 1024 / 1024)}MB 上限，请使用桌面版`);
  }
  const sec = fileLike.durationSec;
  if (sec != null && sec > MAX_VIDEO_SECONDS) {
    throw new AppError("视频处理失败", `时长超过 ${MAX_VIDEO_SECONDS} 秒上限，请使用桌面版`);
  }
}
```

```js
// web/lib/video_bridge.js
import { AppError } from "./errors.js";

const FFMPEG_URL = "https://cdn.jsdelivr.net/npm/@ffmpeg/ffmpeg@0.12.10/dist/umd/ffmpeg.js";
const UTIL_URL = "https://cdn.jsdelivr.net/npm/@ffmpeg/util@0.12.1/dist/umd/index.js";

let loadPromise = null;
let ffmpeg = null;

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload = () => resolve();
    s.onerror = () => reject(new AppError("视频处理失败", `无法加载依赖: ${src}`));
    document.head.appendChild(s);
  });
}

export async function ensureFFmpeg(onStatus) {
  if (ffmpeg) return ffmpeg;
  if (!loadPromise) {
    loadPromise = (async () => {
      if (onStatus) onStatus("正在加载视频引擎…");
      await loadScript(UTIL_URL);
      await loadScript(FFMPEG_URL);
      const { FFmpeg } = globalThis.FFmpegWASM;
      const inst = new FFmpeg();
      if (onStatus) onStatus("正在下载核心（可能需数 MB）…");
      await inst.load({
        coreURL: (await import("https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.6/dist/umd/ffmpeg-core.js")).default
          ? undefined
          : undefined,
      }).catch(async () => {
        // 0.12 load API accepts URL strings via toBlobURL — use util if present
        const { toBlobURL } = globalThis.FFmpegUtil;
        const base = "https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.6/dist/umd";
        await inst.load({
          coreURL: await toBlobURL(`${base}/ffmpeg-core.js`, "text/javascript"),
          wasmURL: await toBlobURL(`${base}/ffmpeg-core.wasm`, "application/wasm"),
        });
      });
      ffmpeg = inst;
      return inst;
    })().catch((e) => {
      loadPromise = null;
      throw e instanceof AppError ? e : new AppError("视频处理失败", String(e));
    });
  }
  return loadPromise;
}

/**
 * Run one ffmpeg invocation. args exclude binary name.
 * Writes output to virtual FS path `outPath`.
 */
export async function runFFmpeg({ args, outPath, onProgress, cancelToken }) {
  const ff = await ensureFFmpeg((s) => onProgress && onProgress(-1, s));
  if (cancelToken && cancelToken.cancelled) throw new AppError("视频处理失败", "已取消");
  const { spawn } = ff;
  // progress via on("progress") when available
  const off = ff.on?.("progress", ({ progress }) => {
    if (onProgress && progress != null) onProgress(Math.max(0, Math.min(100, Math.round(progress * 100))), null);
  });
  try {
    const code = await ff.exec(args);
    if (cancelToken && cancelToken.cancelled) throw new AppError("视频处理失败", "已取消");
    if (code !== 0 && code != null) {
      throw new AppError("视频处理失败", `FFmpeg 编码失败（code ${code}）`);
    }
    if (onProgress) onProgress(100, null);
  } finally {
    if (typeof off === "function") off();
    else if (ff.off) ff.off("progress", () => {});
  }
}

export async function writeFileFromBlob(ff, path, blob) {
  const buf = new Uint8Array(await blob.arrayBuffer());
  await ff.writeFile(path, buf);
  return path;
}

export async function readFileToBlob(ff, path) {
  const data = await ff.readFile(path);
  const bytes = data instanceof Uint8Array ? data : new Uint8Array(data);
  const type = path.endsWith(".gif")
    ? "image/gif"
    : path.endsWith(".png")
      ? "image/png"
      : path.endsWith(".webm")
        ? "video/webm"
        : "video/mp4";
  return new Blob([bytes], { type });
}
```

Implementer note: if the dynamic `import()` of `ffmpeg-core.js` UMD path is wrong for 0.12, **use only** `toBlobURL` path (second branch) and delete the broken first attempt. Pin `@ffmpeg/core@0.12.6`. Cores must be loaded via `toBlobURL` so COEP/cross-origin isolation issues on Pages are avoided when possible; if Pages needs COEP headers, add `web/_headers`:

```
/*
  Cross-Origin-Opener-Policy: same-origin
  Cross-Origin-Embedder-Policy: require-corp
```

Prefer testing without `_headers` first; add only if wasm fails to load.

```js
// web/pages/video.js
import { assertVideoLimits, MAX_VIDEO_BYTES, MAX_VIDEO_SECONDS } from "../lib/video_limits.js";
import { ensureFFmpeg, readFileToBlob, runFFmpeg, writeFileFromBlob } from "../lib/video_bridge.js";
import { createJobList } from "../lib/joblist.js";
import { downloadBlob, stem } from "../lib/download.js";
import { friendlyError, AppError } from "../lib/errors.js";

export function mountVideo(root) {
  root.innerHTML = `
    <div class="note">
      视频引擎按需加载（约数十 MB，首次较慢）。单文件 ≤ ${Math.round(MAX_VIDEO_BYTES / 1024 / 1024)}MB 且 ≤ ${MAX_VIDEO_SECONDS}s，超出请用桌面版。
      去水印请用桌面版。
    </div>
    <div class="row">
      <label>模式
        <select id="mode">
          <option value="convert">格式互转</option>
          <option value="gif">视频转 GIF</option>
          <option value="frames">截取帧</option>
          <option value="trim">片段截取</option>
        </select>
      </label>
      <label id="fmtw">输出
        <select id="fmt">
          <option value="mp4">MP4</option>
          <option value="webm">WebM</option>
        </select>
      </label>
      <label id="gifw" hidden>帧率 <input type="number" id="fps" min="1" max="50" value="15" /></label>
      <label id="gifw2" hidden>宽度 <input type="number" id="gw" min="16" max="3840" value="480" /></label>
      <label id="everyw" hidden>每N秒 <input type="number" id="every" min="0.1" step="0.1" value="1" /></label>
      <label id="trimw" hidden>起(s) <input type="number" id="t0" min="0" step="0.1" value="0" />
        止(s) <input type="number" id="t1" min="0.1" step="0.1" value="5" /></label>
      <label>文件 <input type="file" id="files" accept="video/*,.mp4,.webm,.mov,.mkv" multiple /></label>
      <button type="button" class="btn" id="start">开始转换</button>
    </div>
    <div id="jobs"></div>
    <pre class="err" id="err"></pre>
  `;
  const $ = (id) => root.querySelector(`#${id}`);
  const token = { cancelled: false };
  const jobs = createJobList(root.querySelector("#jobs"), {
    onCancel() {
      token.cancelled = true;
    },
  });

  function syncMode() {
    const m = $("mode").value;
    $("fmtw").hidden = m !== "convert";
    $("gifw").hidden = m !== "gif";
    $("gifw2").hidden = m !== "gif";
    $("everyw").hidden = m !== "frames";
    $("trimw").hidden = m !== "trim";
    $("start").textContent =
      m === "convert" ? "开始转换" : m === "gif" ? "转 GIF" : m === "frames" ? "截取帧" : "片段截取";
  }
  $("mode").addEventListener("change", syncMode);
  syncMode();

  $("start").addEventListener("click", async () => {
    const err = $("err");
    err.textContent = "";
    token.cancelled = false;
    let files = [...$("files").files];
    if (!files.length) {
      err.textContent = "请先添加视频文件";
      return;
    }
    const mode = $("mode").value;
    if (mode === "trim" && files.length > 1) {
      err.textContent = "片段截取一次请选择一个视频";
      return;
    }
    for (const f of files) {
      try {
        assertVideoLimits(f);
      } catch (e) {
        err.textContent = friendlyError(e);
        return;
      }
    }
    jobs.submit(files.map((f, i) => ({ id: i, name: f.name })));
    try {
      await ensureFFmpeg((msg) => setStatusMsg(msg));
    } catch (e) {
      err.textContent = friendlyError(e);
      jobs.finish();
      return;
    }
    for (let i = 0; i < files.length; i++) {
      if (token.cancelled || jobs.cancelled) {
        jobs.setStatus(i, "cancelled", "已取消");
        continue;
      }
      jobs.setStatus(i, "running");
      try {
        await processOne(files[i], mode, (p) => jobs.setProgress(p));
        jobs.setStatus(i, "done");
      } catch (e) {
        const msg = friendlyError(e);
        jobs.setStatus(i, msg === "已取消" ? "cancelled" : "failed", msg);
        if (msg === "已取消") continue;
      }
    }
    jobs.finish();
  });

  async function processOne(file, mode, onPct) {
    const ff = await ensureFFmpeg();
    const inName = `in_${file.name.replace(/[^\w.-]+/g, "_")}`;
    await writeFileFromBlob(ff, inName, file);
    const base = stem(file.name);
    if (mode === "convert") {
      const ext = $("fmt").value;
      const out = `out.${ext}`;
      const args =
        ext === "webm"
          ? ["-i", inName, "-c:v", "libvpx-vp9", "-b:v", "1M", "-an", out]
          : ["-i", inName, "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", out];
      await runFFmpeg({ args, outPath: out, onProgress: onPct, cancelToken: token });
      downloadBlob(await readFileToBlob(ff, out), `${base}.${ext}`);
    } else if (mode === "gif") {
      const out = `${base}.gif`;
      const args = [
        "-i", inName, "-an",
        "-vf",
        `fps=${$("fps").value},scale=${$("gw").value}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer`,
        out,
      ];
      await runFFmpeg({ args, outPath: out, onProgress: onPct, cancelToken: token });
      downloadBlob(await readFileToBlob(ff, out), out);
    } else if (mode === "frames") {
      const pattern = `frame_%04d.png`;
      const args = ["-i", inName, "-vf", `fps=1/${$("every").value}`, pattern];
      await runFFmpeg({ args, outPath: pattern, onProgress: onPct, cancelToken: token });
      // read all frames into zip
      const names = await listFiles(ff, /frame_\d+\.png$/);
      await ensureJszipV();
      const zip = new globalThis.JSZip();
      for (const n of names) zip.file(n, await readFileToBlob(ff, n));
      downloadBlob(await zip.generateAsync({ type: "blob" }), `${base}_frames.zip`);
    } else {
      const out = `${base}_trim.mp4`;
      const args = [
        "-ss", String($("t0").value), "-to", String($("t1").value), "-i", inName,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", out,
      ];
      await runFFmpeg({ args, outPath: out, onProgress: onPct, cancelToken: token });
      downloadBlob(await readFileToBlob(ff, out), out);
    }
    try {
      await ff.deleteFile(inName);
    } catch { /* ignore */ }
  }
}

async function listFiles(ff, re) {
  try {
    const names = await ff.listDir("/");
    return (names || []).map((x) => (typeof x === "string" ? x : x.name)).filter((n) => re.test(n));
  } catch {
    return [];
  }
}

function setStatusMsg(msg) {
  const el = document.getElementById("status");
  if (el && msg) el.textContent = msg;
}

async function ensureJszipV() {
  if (globalThis.JSZip) return;
  await new Promise((res, rej) => {
    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js";
    s.onload = res;
    s.onerror = rej;
    document.head.appendChild(s);
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test web/tests/video_limits.test.mjs`  
Expected: PASS

- [ ] **Step 5: Manual smoke** — tiny MP4 convert + gif + cancel + over-limit file rejection.

- [ ] **Step 6: Commit**

```bash
git add web/lib/video_bridge.js web/lib/video_limits.js web/pages/video.js web/tests/video_limits.test.mjs
git commit -m "feat(web): video page with ffmpeg.wasm"
```

---

### Task 10: Full test suite + desktop regression + Pages notes

**Files:**
- Create: `web/tests/run-all.mjs` (or use `node --test web/tests`)
- Create: `web/README.md` (deploy notes only)
- Modify: none required in desktop

**Interfaces:**
- Consumes: all previous
- Produces: documented commands for CI/humans

- [ ] **Step 1: Run all web tests**

Run: `node --test web/tests`  
Expected: all PASS

- [ ] **Step 2: Desktop regression**

Run: `python -m pytest -q`  
Expected: 60 passed (or more if desktop still has same tests)

- [ ] **Step 3: Write `web/README.md`**

```markdown
# Wallpaper Converter Web

静态网页版。Cloudflare Pages：

- Root directory: `web`
- Build command: (empty)
- Output directory: (empty / root)

本地预览：`python -m http.server 8765 -d web`

测试：`node --test web/tests`
```

- [ ] **Step 4: Commit**

```bash
git add web/README.md web/tests
git commit -m "chore(web): tests green, Pages deploy notes"
```

- [ ] **Step 5: Push with proxy**

```bash
$env:HTTPS_PROXY=$env:HTTP_PROXY="http://127.0.0.1:7897"
git push origin main
```

Expected: push succeeds.

---

### Task 11: (Optional follow-up) Cloudflare Pages project attach

Not code in repo unless using Wrangler. Document only:

- User creates Pages project linked to `sun-zihang/wallpaper-forge`
- Root = `web`
- First deploy after push; verify HTTPS four pages + home watermark CTA link.

If using Wrangler later, add `wrangler.toml` at repo root — **out of scope unless requested**.

---

## Self-Review

**Spec coverage**

| Spec item | Task |
|-----------|------|
| Scaffold / home / privacy note / desktop watermark CTA | 1 |
| Errors, job list, download | 2 |
| Image convert/crop/watermark | 3, 6 |
| GIF split/merge | 4, 7 |
| WE pkg/tex/mpkg | 5, 8 |
| Video limits + wasm + progress/cancel | 9 |
| Tests + desktop green + Pages notes | 10–11 |
| No workers/backend | Global constraints |
| CDN pins | Global constraints |

**Placeholder scan** — no TBD/TODO; video core load has an explicit fallback rule for implementer; GIF encoder has explicit gifenc fallback rule.

**Type consistency** — `AppError(label, detail)`, `createJobList` API, `friendlyError`, status strings consistent across tasks 2–9.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-23-wallpaper-web-cloudbase.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute in this session with checkpoints  

Which approach?
