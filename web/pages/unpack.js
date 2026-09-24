// web/pages/unpack.js
import { extractMpkg } from "../lib/we_mpkg.js";
import { extractPkg } from "../lib/we_pkg.js";
import { extractTex } from "../lib/we_tex.js";
import { detectKind } from "../lib/we_detect.js";
import { createJobList } from "../lib/joblist.js";
import { batchPct } from "../lib/progress.js";
import { validateSelection } from "../lib/selection.js";
import { attachDropTarget } from "../lib/drop.js";
import { downloadBlob, stem } from "../lib/download.js";
import { friendlyError, AppError } from "../lib/errors.js";

const WE_EXTS = [".pkg", ".tex", ".mpkg"];

export function mountUnpack(root) {
  root.innerHTML = `
    <div class="page-head">
      <h1>解包</h1>
      <p>识别 <code>.pkg</code> / <code>.tex</code> / <code>.mpkg</code> 并列出产物，打包下载。</p>
    </div>
    <div class="drop-bay" id="dropzone">
      <div class="row">
        <div class="field">
          <label for="files">选择文件</label>
          <input type="file" id="files" multiple accept=".pkg,.tex,.mpkg" />
        </div>
        <span class="drop-hint">或拖拽到此处</span>
      </div>
    </div>
    <div class="panel">
      <div class="row">
        <button type="button" class="btn" id="start">开始解包</button>
        <button type="button" class="btn secondary" id="dl">打包下载 ZIP</button>
      </div>
    </div>
    <div id="jobs"></div>
    <pre class="err" id="err"></pre>
  `;
  const $ = (id) => root.querySelector(`#${id}`);
  const jobs = createJobList(root.querySelector("#jobs"), { onCancel() {} });
  let allFiles = [];
  let running = false;
  let zipping = false;

  attachDropTarget($("dropzone"), $("files"), {
    extensions: WE_EXTS,
    onRejected: (msg) => {
      $("err").textContent = msg;
    },
  });

  $("start").addEventListener("click", async () => {
    if (running || zipping) return;
    $("err").textContent = "";
    const picked = [...$("files").files];
    if (!picked.length) {
      $("err").textContent = "请先添加 .pkg / .tex / .mpkg 文件";
      return;
    }
    const check = validateSelection(picked, { extensions: WE_EXTS });
    if (!check.ok) {
      $("err").textContent = check.errors.map((e) => `${e.name}：${e.reason}`).join("\n");
      return;
    }
    const files = check.files;
    running = true;
    $("start").disabled = true;
    $("dl").disabled = true;
    try {
      jobs.submit(files.map((f, i) => ({ id: i, name: f.name })));
      allFiles = [];
      for (let i = 0; i < files.length; i++) {
        if (jobs.cancelled) {
          jobs.setStatus(i, "cancelled", "已取消");
          continue;
        }
        const f = files[i];
        const kind = detectKind(f.name);
        if (!kind) {
          jobs.setStatus(i, "failed", "不支持的文件类型，该变体请用桌面版");
          continue;
        }
        jobs.setStatus(i, "running");
        jobs.setProgress(batchPct(i, 0, files.length));
        try {
          const buf = new Uint8Array(await f.arrayBuffer());
          const base = stem(f.name);
          let result;
          if (kind === "pkg") result = extractPkg(buf);
          else if (kind === "tex") result = { files: [extractTex(buf, base)] };
          else result = extractMpkg(buf);
          for (const item of result.files) allFiles.push(item);
          jobs.setStatus(i, "done");
          jobs.setProgress(batchPct(i, 100, files.length));
        } catch (e) {
          jobs.setStatus(i, "failed", friendlyError(e));
        }
      }
      jobs.finish();
    } finally {
      running = false;
      $("start").disabled = false;
      $("dl").disabled = false;
    }
  });

  $("dl").addEventListener("click", async () => {
    if (running || zipping) return;
    zipping = true;
    $("dl").disabled = true;
    try {
      if (!allFiles.length) {
        $("err").textContent = "还没有解包结果";
        return;
      }
      await ensureJszip();
      const zip = new globalThis.JSZip();
      for (const f of allFiles) zip.file(f.name, f.blob);
      downloadBlob(await zip.generateAsync({ type: "blob" }), "unpacked.zip");
    } catch (e) {
      $("err").textContent = friendlyError(e);
    } finally {
      zipping = false;
      $("dl").disabled = false;
    }
  });
}

function ensureJszip() {
  if (globalThis.JSZip) return Promise.resolve();
  return new Promise((res, rej) => {
    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js";
    s.onload = res;
    s.onerror = () => rej(new AppError("PKG 解包失败", "JSZip 加载失败"));
    document.head.appendChild(s);
  });
}
