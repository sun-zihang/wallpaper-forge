// web/pages/unpack.js
import { extractTex } from "../lib/we_tex.js";
import { detectKind } from "../lib/we_detect.js";
import { runJob } from "../lib/worker_client.js";
import { runLimited } from "../lib/pipeline.js";
import { createJobList } from "../lib/joblist.js";
import { batchPct } from "../lib/progress.js";
import { validateSelection } from "../lib/selection.js";
import { JSZIP_URLS, loadScriptFirstOnce } from "../lib/cdn.js";
import { downloadBlob, stem, supportsFileSystemAccess, pickOutputDirectory, saveBlobsToDirectory } from "../lib/download.js";
import { friendlyError, AppError } from "../lib/errors.js";
import { setStatus, getRenderToken, setTaskRunning } from "../app.js";
import { trackEnd, trackFailure, trackStart, trackUpload } from "../lib/track.js";
import { registerShortcutAction } from "../lib/shortcuts.js";
import { showToast } from "../lib/toast.js";
import { reportJob } from "../lib/jobcenter.js";

const WE_EXTS = [".pkg", ".tex", ".mpkg"];

export function mountUnpack(root) {
  root.innerHTML = `
    <div class="page-head">
      <h1>项目解包</h1>
      <p>识别 .pkg / .tex / .mpkg 并列出产物。左侧文件，中间信息卡与文件树，右侧导出设置。</p>
    </div>
    <div class="gif-layout">
      <aside class="img-files">
        <div class="img-files-head">
          <span>文件</span>
          <button type="button" class="btn secondary" id="addFiles">添加</button>
          <input type="file" id="files" multiple accept=".pkg,.tex,.mpkg" hidden />
        </div>
        <div class="img-file-list" id="fileList"></div>
      </aside>
      <div class="unpack-main">
        <div class="info-card" id="infoCard" hidden>
          <img id="infoPreview" alt="预览" />
          <div class="info-meta" id="infoMeta"></div>
        </div>
        <div class="file-tree" id="fileTree"></div>
        <div class="tex-preview" id="texPreview" hidden>
          <p class="panel-title">TEX 纹理预览</p>
          <img id="texImg" alt="纹理" />
          <div class="info-meta" id="texMeta"></div>
        </div>
      </div>
      <div class="unpack-params">
        <div class="panel">
          <p class="panel-title">导出设置</p>
          <div class="row">
            <div class="field">
              <label for="texFmt">TEX 导出格式</label>
              <select id="texFmt">
                <option value=".png">PNG（无损）</option>
                <option value=".jpg">JPG（有损）</option>
                <option value=".webp">WebP</option>
              </select>
            </div>
            <div class="field">
              <label class="inline"><input type="checkbox" id="mipAll" /> 导出所有 Mipmap 层级</label>
            </div>
            <div class="field">
              <label class="inline"><input type="checkbox" id="scale4k" checked /> 缩放至最大 4K</label>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="img-actionbar">
      <button type="button" class="btn" id="start">开始解包</button>
      <button type="button" class="btn secondary" id="retry" hidden>重试失败</button>
      <button type="button" class="btn secondary" id="dl">打包下载 ZIP</button>
      <button type="button" class="btn secondary" id="savedir" hidden>保存到文件夹</button>
      <span class="actionbar-pct" id="actionbarPct"></span>
    </div>
    <div id="jobs"></div>
    <pre class="err" id="err"></pre>
  `;
  const $ = (id) => root.querySelector(`#${id}`);
  const jobs = createJobList(root.querySelector("#jobs"), {
    onCancel() {},
    onReport: (job) => reportJob({ ...job, id: `unpack:${job.id}`, page: "解包" }),
  });
  let allFiles = [];
  let lastBatch = null;
  let running = false;
  let zipping = false;
  let saving = false;
  let selectedFile = null;
  const pageToken = getRenderToken();

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

  $("addFiles").addEventListener("click", () => $("files").click());
  $("files").addEventListener("change", () => {
    const picked = [...$("files").files];
    $("files").value = "";
    addFiles(picked);
  });

  if (window.__wcHandoff && window.__wcHandoff.length) {
    const handoff = window.__wcHandoff;
    window.__wcHandoff = null;
    addFiles(handoff);
  }

  const fileList = $("fileList");
  const fileEntries = [];

  const filesAside = root.querySelector(".img-files");
  filesAside.addEventListener("dragover", (ev) => {
    ev.preventDefault();
    filesAside.classList.add("hot");
  });
  filesAside.addEventListener("dragleave", () => filesAside.classList.remove("hot"));
  filesAside.addEventListener("drop", (ev) => {
    ev.preventDefault();
    filesAside.classList.remove("hot");
    addFiles([...(ev.dataTransfer?.files || [])]);
  });

  function addFiles(files) {
    let pushed = 0;
    for (const f of files) {
      const check = validateSelection([f], { extensions: WE_EXTS });
      if (!check.ok) {
        $("err").textContent = check.errors.map((e) => `${e.name}：${e.reason}`).join("\n");
        continue;
      }
      pushed += 1;
      fileEntries.push({ file: f, status: "pending" });
    }
    if (pushed) trackUpload(pushed);
    renderFileList();
    if (fileEntries.length && !selectedFile) selectFile(fileEntries[0]);
  }

  function renderFileList() {
    fileList.innerHTML = "";
    fileEntries.forEach((entry) => {
      const div = document.createElement("div");
      div.className = `img-file${entry === selectedFile ? " selected" : ""}`;
      const icon = { pending: "🔘", running: "⚙️", done: "✅", failed: "❌", cancelled: "⏹" }[entry.status] || "🔘";
      div.innerHTML = `<span class="img-file-icon">${icon}</span><span class="img-file-name"></span>`;
      div.querySelector(".img-file-name").textContent = entry.file.name;
      div.addEventListener("click", () => selectFile(entry));
      fileList.appendChild(div);
    });
  }

  function setFileStatus(entry, status) {
    entry.status = status;
    renderFileList();
  }

  function selectFile(entry) {
    selectedFile = entry;
    renderFileList();
    $("infoCard").hidden = true;
    $("texPreview").hidden = true;
  }

  function buildTree(files) {
    const root = { name: "", children: {}, files: [] };
    for (const f of files) {
      const parts = f.name.split("/");
      let node = root;
      for (let i = 0; i < parts.length - 1; i++) {
        const p = parts[i];
        if (!node.children[p]) node.children[p] = { name: p, children: {}, files: [] };
        node = node.children[p];
      }
      node.files.push(f);
    }
    return root;
  }

  function renderTree(node, container, depth) {
    const folders = Object.values(node.children).sort((a, b) => a.name.localeCompare(b.name));
    for (const folder of folders) {
      const folderEl = document.createElement("details");
      folderEl.className = "tree-folder";
      folderEl.open = depth < 1;
      const summary = document.createElement("summary");
      summary.textContent = `📁 ${folder.name}`;
      folderEl.appendChild(summary);
      const inner = document.createElement("div");
      inner.className = "tree-inner";
      renderTree(folder, inner, depth + 1);
      folderEl.appendChild(inner);
      container.appendChild(folderEl);
    }
    const files = [...node.files].sort((a, b) => a.name.localeCompare(b.name));
    for (const f of files) {
      const row = document.createElement("div");
      row.className = "tree-file";
      const isTex = f.name.toLowerCase().endsWith(".tex");
      const icon = isTex ? "🖼️" : f.name.match(/\.(png|jpe?g|webp)$/i) ? "🖼️" : f.name.match(/\.(mp4|webm)$/i) ? "🎬" : f.name.match(/\.(mp3|wav|aac)$/i) ? "🎵" : "📄";
      row.innerHTML = `<span>${icon}</span><span class="tree-name"></span><span class="tree-size"></span>`;
      row.querySelector(".tree-name").textContent = f.name.split("/").pop();
      row.querySelector(".tree-size").textContent = formatSize(f.blob);
      if (isTex) {
        const btn = document.createElement("button");
        btn.className = "btn secondary";
        btn.textContent = "▶";
        btn.addEventListener("click", (ev) => {
          ev.stopPropagation();
          previewTex(f);
        });
        row.appendChild(btn);
      }
      row.addEventListener("click", () => {
        if (isTex) previewTex(f);
        else downloadBlob(toBlob(f.blob), f.name.split("/").pop());
      });
      container.appendChild(row);
    }
  }

  function formatSize(b) {
    const n = b && (b.size != null ? b.size : b.length) || 0;
    if (n < 1024) return `${n}B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)}KB`;
    return `${(n / 1024 / 1024).toFixed(1)}MB`;
  }

  function toBlob(b) {
    return b instanceof Blob ? b : new Blob([b]);
  }

  async function previewTex(f) {
    try {
      const buf = new Uint8Array(await f.file.arrayBuffer());
      if (pageToken !== getRenderToken()) return;
      const base = stem(f.name);
      const extracted = extractTex(buf, base);
      const url = URL.createObjectURL(toBlob(extracted.blob));
      $("texImg").src = url;
      const bmp = await loadImageBitmapSafe(toBlob(extracted.blob));
      const dims = bmp ? `${bmp.width}×${bmp.height}` : "未知";
      const fmt = extracted.name.split(".").pop().toUpperCase();
      $("texMeta").innerHTML = `<div>格式: ${fmt}</div><div>尺寸: ${dims}</div>      <div>大小: ${formatSize(extracted.blob)}</div>`;
      $("texPreview").hidden = false;
    } catch (e) {
      $("err").textContent = friendlyError(e);
    }
  }

  async function loadImageBitmapSafe(blob) {
    try {
      return await createImageBitmap(blob);
    } catch {
      return null;
    }
  }

  function showInfoCard() {
    const img = allFiles.find((f) => f.name.match(/\.(png|jpe?g|webp)$/i));
    if (!img) {
      $("infoCard").hidden = true;
      return;
    }
    $("infoPreview").src = URL.createObjectURL(toBlob(img.blob));
    const dims = img.name.match(/\.(png|jpe?g|webp)$/i) ? "" : "";
    $("infoMeta").innerHTML = `
      <div>文件: ${img.name.split("/").pop()}</div>
      <div>大小: ${formatSize(img.blob)}</div>
      <div>产物总数: ${allFiles.length}</div>
    `;
    $("infoCard").hidden = false;
  }

  function stale() {
    return pageToken !== getRenderToken();
  }

  $("start").addEventListener("click", async () => {
    if (running || zipping) return;
    $("err").textContent = "";
    const files = fileEntries.map((e) => e.file);
    if (!files.length) {
      $("err").textContent = "请先添加 .pkg / .tex / .mpkg 文件";
      return;
    }
    const check = validateSelection(files, { extensions: WE_EXTS });
    if (!check.ok) {
      $("err").textContent = check.errors.map((e) => `${e.name}：${e.reason}`).join("\n");
      return;
    }
    lastBatch = files;
    running = true;
    setTaskRunning(true);
    const t0 = trackStart();
    $("start").disabled = true;
    $("dl").disabled = true;
    try {
      jobs.submit(files.map((f, i) => ({ id: i, name: f.name })));
      allFiles = [];
      await runLimited(
        files.length,
        async (i) => {
          if (jobs.cancelled) {
            jobs.setStatus(i, "cancelled", "已取消");
            return;
          }
          const f = files[i];
          const kind = detectKind(f.name);
          if (!kind) {
            jobs.setStatus(i, "failed", "不支持的文件类型，该变体请用桌面版");
            return;
          }
          jobs.setStatus(i, "running");
          jobs.setProgress(batchPct(i, 0, files.length));
          jobs.setBatch(i, files.length, f.name);
          try {
            const result = await runJob(`unpack_${kind}`, { file: f });
            for (const item of result.files) allFiles.push(item);
            jobs.setStatus(i, "done");
            jobs.setProgress(batchPct(i, 100, files.length));
          } catch (e) {
            trackFailure(e);
            jobs.setStatus(i, "failed", friendlyError(e));
          }
        },
        { limit: 2, shouldStop: () => jobs.cancelled },
      );
      jobs.finish();
      if (!stale()) {
        $("retry").hidden = jobs.failedIndices().length === 0;
        const tree = buildTree(allFiles);
        const treeEl = $("fileTree");
        treeEl.innerHTML = "";
        renderTree(tree, treeEl, 0);
        showInfoCard();
        if (allFiles.length) showToast(`解包完成，共 ${allFiles.length} 个文件`, "success");
        syncSaveDir();
      }
    } finally {
      running = false;
      setTaskRunning(false);
      trackEnd(t0);
      if (!stale()) {
        $("start").disabled = false;
        $("dl").disabled = false;
      }
    }
  });

  $("retry").addEventListener("click", async () => {
    if (!lastBatch || running || zipping) return;
    const failedIdx = jobs.failedIndices();
    if (!failedIdx.length) return;
    running = true;
    setTaskRunning(true);
    const t0 = trackStart();
    $("start").disabled = true;
    $("dl").disabled = true;
    $("retry").disabled = true;
    try {
      await runLimited(
        failedIdx.length,
        async (k) => {
          const i = failedIdx[k];
          if (jobs.cancelled) {
            jobs.setStatus(i, "cancelled", "已取消");
            return;
          }
          const f = lastBatch[i];
          const kind = detectKind(f.name);
          if (!kind) {
            jobs.setStatus(i, "failed", "不支持的文件类型，该变体请用桌面版");
            return;
          }
          jobs.setStatus(i, "running");
          jobs.setProgress(batchPct(i, 0, lastBatch.length));
          jobs.setBatch(i, lastBatch.length, f.name);
          try {
            const result = await runJob(`unpack_${kind}`, { file: f });
            for (const item of result.files) allFiles.push(item);
            jobs.setStatus(i, "done");
            jobs.setProgress(batchPct(i, 100, lastBatch.length));
          } catch (e) {
            trackFailure(e);
            jobs.setStatus(i, "failed", friendlyError(e));
          }
        },
        { limit: 2, shouldStop: () => jobs.cancelled },
      );
      jobs.finish();
      if (!stale()) {
        $("retry").hidden = jobs.failedIndices().length === 0;
        const tree = buildTree(allFiles);
        const treeEl = $("fileTree");
        treeEl.innerHTML = "";
        renderTree(tree, treeEl, 0);
        showInfoCard();
        syncSaveDir();
      }
    } finally {
      running = false;
      setTaskRunning(false);
      trackEnd(t0);
      if (!stale()) {
        $("start").disabled = false;
        $("dl").disabled = false;
        $("retry").disabled = false;
      }
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
      jobs.setZipProgress(0, "unpacked.zip");
      const blob = await zip.generateAsync({ type: "blob" }, (meta) =>
        jobs.setZipProgress(meta.percent, "unpacked.zip")
      );
      downloadBlob(blob, "unpacked.zip");
    } catch (e) {
      $("err").textContent = friendlyError(e);
    } finally {
      zipping = false;
      $("dl").disabled = false;
    }
  });

  $("savedir").addEventListener("click", async () => {
    if (running || zipping || saving || !allFiles.length) return;
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

  function syncSaveDir() {
    const btn = $("savedir");
    if (btn) btn.hidden = !supportsFileSystemAccess() || allFiles.length === 0;
  }

  async function ensureJszip() {
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
}
