// web/pages/unpack.js
import { extractMpkg } from "../lib/we_mpkg.js";
import { extractPkg } from "../lib/we_pkg.js";
import { extractTex } from "../lib/we_tex.js";
import { detectKind } from "../lib/we_detect.js";
import { createJobList } from "../lib/joblist.js";
import { batchPct } from "../lib/progress.js";
import { validateSelection } from "../lib/selection.js";
import { attachDropTarget } from "../lib/drop.js";
import { JSZIP_URLS, loadScriptFirstOnce } from "../lib/cdn.js";
import { downloadBlob, stem, supportsFileSystemAccess, pickOutputDirectory, saveBlobsToDirectory } from "../lib/download.js";
import { friendlyError, AppError } from "../lib/errors.js";
import { setStatus } from "../app.js";
import { registerShortcutAction } from "../lib/shortcuts.js";
import { showToast } from "../lib/toast.js";

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
        <button type="button" class="btn secondary" id="savedir" hidden>保存到文件夹</button>
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
  let saving = false;

  function syncSaveDir() {
    const btn = $("savedir");
    if (btn) btn.hidden = !supportsFileSystemAccess() || allFiles.length === 0;
  }

  registerShortcutAction("onOpen", () => $("files").click());
  registerShortcutAction("onStart", () => {
    if (!running) $("start").click();
  });
  registerShortcutAction("onDownload", () => {
    if (allFiles.length) $("dl").click();
  });
  registerShortcutAction("onCancel", () => {
    const btn = root.querySelector('[data-act="cancel"]');
    if (btn && !btn.disabled) btn.click();
  });

  attachDropTarget($("dropzone"), $("files"), {
    extensions: WE_EXTS,
    onRejected: (msg) => {
      $("err").textContent = msg;
    },
  });

  if (window.__wcHandoff && window.__wcHandoff.length) {
    const handoff = window.__wcHandoff;
    window.__wcHandoff = null;
    const dt = new DataTransfer();
    for (const f of handoff) dt.items.add(f);
    $("files").files = dt.files;
    $("files").dispatchEvent(new Event("change", { bubbles: true }));
  }

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
          syncSaveDir();
        } catch (e) {
          jobs.setStatus(i, "failed", friendlyError(e));
        }
      }
      jobs.finish();
      if (allFiles.length) showToast(`解包完成，共 ${allFiles.length} 个文件`, "success");
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

  $("savedir").addEventListener("click", async () => {
    if (running || zipping || saving || !allFiles.length) return;
    $("err").textContent = "";
    saving = true;
    $("savedir").disabled = true;
    try {
      const dir = await pickOutputDirectory();
      const written = await saveBlobsToDirectory(dir, allFiles);
      setStatus(`已保存 ${written.length} 个文件到所选文件夹`);
    } catch (e) {
      if (!(e instanceof AppError && e.detail === "已取消选择")) {
        $("err").textContent = friendlyError(e);
      }
    } finally {
      saving = false;
      $("savedir").disabled = false;
    }
  });
}

function ensureJszip() {
  if (globalThis.JSZip) return Promise.resolve();
  return loadScriptFirstOnce(JSZIP_URLS)
    .then(() => {
      if (!globalThis.JSZip) throw new AppError("解包失败", "JSZip 加载失败");
    })
    .catch((e) => {
      if (e instanceof AppError) throw e;
      throw new AppError("解包失败", `无法加载依赖: ${JSZIP_URLS.join(" / ")}`);
    });
}
