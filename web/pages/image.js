// web/pages/image.js
import { OUT_FORMATS, IMAGE_EXTS, loadImageBitmap } from "../lib/image_ops.js";
import { assertImageResolution } from "../lib/validate.js";
import { cropCanvas } from "../lib/annotate.js";
import { cancelAllWorkerJobs, runJob } from "../lib/worker_client.js";
import { runLimited } from "../lib/pipeline.js";
import { createJobList } from "../lib/joblist.js";
import { batchPct } from "../lib/progress.js";
import { validateSelection } from "../lib/selection.js";
import { JSZIP_URLS, loadScriptFirstOnce } from "../lib/cdn.js";
import { downloadBlob, stem, supportsFileSystemAccess, pickOutputDirectory, saveBlobsToDirectory } from "../lib/download.js";
import { friendlyError, AppError } from "../lib/errors.js";
import { validateImageFile } from "../lib/validate.js";
import { setStatus, getRenderToken, setTaskRunning } from "../app.js";
import { registerShortcutAction } from "../lib/shortcuts.js";
import { showToast } from "../lib/toast.js";
import { loadSettings, saveSettings } from "../lib/settings.js";
import { reportJob } from "../lib/jobcenter.js";
import { trackEnd, trackFailure, trackStart, trackUpload } from "../lib/track.js";

export function mountImage(root) {
  root.innerHTML = `
    <div class="page-head">
      <h1>图片转换</h1>
      <p>格式互转、等比缩放、裁剪与水印。左侧文件列表，中间实时预览（可对比），右侧参数。</p>
    </div>
    <div class="img-layout">
      <aside class="img-files">
        <div class="img-files-head">
          <span>文件</span>
          <button type="button" class="btn secondary" id="addFiles">添加</button>
          <input type="file" id="files" multiple accept="image/*" hidden />
        </div>
        <div class="img-file-list" id="fileList"></div>
      </aside>
      <div class="img-preview">
        <div class="preview-stage" id="stage">
          <canvas id="previewCanvas"></canvas>
          <div class="compare-handle" id="compareHandle" hidden></div>
          <div class="preview-empty" id="previewEmpty">选择左侧文件预览</div>
        </div>
        <div class="preview-bar">
          <label class="inline"><input type="checkbox" id="compare" /> 对比</label>
          <span class="preview-info" id="previewInfo"></span>
        </div>
      </div>
      <div class="img-params">
        <div class="panel">
          <p class="panel-title">转换设置</p>
          <div class="row">
            <div class="field">
              <label for="fmt">输出格式</label>
              <select id="fmt">${OUT_FORMATS.map((f) => `<option${f === "JPG" ? " selected" : ""}>${f}</option>`).join("")}</select>
            </div>
            <div class="field">
              <label for="q">质量 <span id="qv">90</span></label>
              <input type="range" id="q" min="1" max="100" value="90" />
            </div>
            <div class="field">
              <label class="inline"><input type="checkbox" id="scale" /> 缩放到宽度</label>
              <input type="number" id="sw" value="1920" min="16" max="8192" disabled />
            </div>
          </div>
        </div>
        <div class="panel">
          <p class="panel-title">水印（批量）</p>
          <div class="row">
            <div class="field">
              <label>类型</label>
              <span class="row">
                <button type="button" class="btn secondary active" id="wmtext">文字水印</button>
                <button type="button" class="btn secondary" id="wmimg">图片水印…</button>
              </span>
            </div>
            <div class="field" id="wm_text_field">
              <label for="wm_text">文字</label>
              <input type="text" id="wm_text" value="我的壁纸" />
            </div>
            <div class="field">
              <label for="wm_size">字号 <span id="wm_size_v">32</span></label>
              <input type="number" id="wm_size" min="8" max="400" value="32" />
            </div>
            <div class="field" id="wm_scale_field" hidden>
              <label for="wm_scale">缩放 <span id="wm_scale_v">20%</span></label>
              <input type="range" id="wm_scale" min="5" max="100" value="20" />
            </div>
            <div class="field">
              <label for="wm_opacity">透明度 <span id="wm_opacity_v">70%</span></label>
              <input type="range" id="wm_opacity" min="5" max="100" value="70" />
            </div>
            <div class="field">
              <label for="wm_pos">位置</label>
              <select id="wm_pos">
                <option value="bottom_right">右下</option>
                <option value="bottom_left">左下</option>
                <option value="top_right">右上</option>
                <option value="top_left">左上</option>
                <option value="center">居中</option>
              </select>
            </div>
          </div>
          <div class="row">
            <button type="button" class="btn" id="wm_apply">应用到全部图片</button>
            <button type="button" class="btn secondary" id="crop">裁剪第一张…</button>
            <input type="file" id="markfile" accept="image/*" hidden />
          </div>
        </div>
      </div>
    </div>
    <div class="img-actionbar">
      <button type="button" class="btn" id="start">开始转换</button>
      <button type="button" class="btn secondary" id="retry" hidden>重试失败</button>
      <button type="button" class="btn secondary" id="zip">打包下载 ZIP</button>
      <button type="button" class="btn secondary" id="savedir" hidden>保存到文件夹</button>
      <span class="actionbar-pct" id="actionbarPct"></span>
    </div>
    <div id="jobs"></div>
    <pre class="err" id="err"></pre>
  `;
  const jobs = createJobList(root.querySelector("#jobs"), {
    onReport: (job) => reportJob({ ...job, id: `image:${job.id}`, page: "图片" }),
  });
  const err = root.querySelector("#err");
  const $ = (id) => root.querySelector(`#${id}`);
  const outputs = [];
  let running = false;
  let zipping = false;
  let saving = false;
  let selectedFile = null;
  let compareOn = false;
  let originalBitmap = null;
  let processedBitmap = null;
  let lastBatch = null;
  const pageToken = getRenderToken();

  function syncSaveDir() {
    const btn = $("savedir");
    if (btn) btn.hidden = !supportsFileSystemAccess() || outputs.length === 0;
  }

  registerShortcutAction("onOpen", () => $("files").click());
  registerShortcutAction("onStart", () => {
    if (!running) $("start").click();
  });
  registerShortcutAction("onDownload", () => {
    if (outputs.length) $("zip").click();
  });
  registerShortcutAction("onCancel", () => {
    const btn = root.querySelector('[data-act="cancel"]');
    if (btn && !btn.disabled) btn.click();
  });

  const settings = loadSettings();
  try {
    const savedFmt = localStorage.getItem("wc.fmt");
    const fmt =
      savedFmt && [...$("fmt").options].some((o) => o.value === savedFmt)
        ? savedFmt
        : settings.imageFormat;
    $("fmt").value = fmt;
    const savedQ = Number(localStorage.getItem("wc.q"));
    const q = savedQ >= 1 && savedQ <= 100 ? savedQ : settings.imageQuality;
    $("q").value = String(q);
    $("qv").textContent = String(q);
    const w = Number(settings.imageWidth);
    if (w >= 16 && w <= 8192) $("sw").value = String(w);
  } catch { /* storage unavailable */ }

  $("addFiles").addEventListener("click", () => $("files").click());
  $("files").addEventListener("change", () => {
    const picked = [...$("files").files];
    $("files").value = "";
    addFiles(picked);
  });

  const fileList = $("fileList");
  const fileEntries = [];
  let addingPromise = null;

  if (window.__wcHandoff && window.__wcHandoff.length) {
    const handoff = window.__wcHandoff;
    window.__wcHandoff = null;
    addFiles(handoff);
  }

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

  async function addFiles(files) {
    const p = (async () => {
      let pushed = 0;
      for (const f of files) {
        const check = validateSelection([f], { extensions: IMAGE_EXTS });
        if (!check.ok) {
          err.textContent = check.errors.map((e) => `${e.name}：${e.reason}`).join("\n");
          continue;
        }
        try {
          const bmp = await loadImageBitmap(f);
          if (pageToken !== getRenderToken()) return;
          assertImageResolution(bmp.width, bmp.height);
          bmp.close && bmp.close();
        } catch (e) {
          if (pageToken !== getRenderToken()) return;
          err.textContent = friendlyError(e);
          continue;
        }
        if (pageToken !== getRenderToken()) return;
        pushed += 1;
        fileEntries.push({ file: f, status: "pending" });
      }
      if (pageToken !== getRenderToken()) return;
      if (pushed) trackUpload(pushed);
      renderFileList();
      if (fileEntries.length && !selectedFile) selectFile(fileEntries[0]);
    })();
    addingPromise = p;
    try {
      await p;
    } finally {
      addingPromise = null;
    }
  }

  function renderFileList() {
    fileList.innerHTML = "";
    fileEntries.forEach((entry, i) => {
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
    loadPreview(entry.file);
  }

  async function loadPreview(file) {
    try {
      if (originalBitmap) originalBitmap.close();
      originalBitmap = await loadImageBitmap(file);
      if (pageToken !== getRenderToken()) return;
      processedBitmap = null;
      $("previewEmpty").hidden = true;
      drawPreview();
      const info = `${originalBitmap.width}×${originalBitmap.height}`;
      $("previewInfo").textContent = info;
    } catch (e) {
      $("previewInfo").textContent = friendlyError(e);
    }
  }

  function drawPreview() {
    const canvas = $("previewCanvas");
    const stage = $("stage");
    if (!originalBitmap) {
      stage.style.aspectRatio = "";
      return;
    }
    const maxW = stage.clientWidth || 600;
    const scale = Math.min(1, maxW / originalBitmap.width);
    const w = Math.max(1, Math.round(originalBitmap.width * scale));
    const h = Math.max(1, Math.round(originalBitmap.height * scale));
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingQuality = "high";
    if (compareOn && processedBitmap) {
      const split = Math.round(w * 0.5);
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, 0, split, h);
      ctx.clip();
      ctx.drawImage(originalBitmap, 0, 0, w, h);
      ctx.restore();
      ctx.save();
      ctx.beginPath();
      ctx.rect(split, 0, w - split, h);
      ctx.clip();
      ctx.drawImage(processedBitmap, 0, 0, w, h);
      ctx.restore();
      const handle = $("compareHandle");
      handle.hidden = false;
      handle.style.left = `${split}px`;
    } else {
      ctx.drawImage(originalBitmap, 0, 0, w, h);
      $("compareHandle").hidden = true;
    }
    stage.style.aspectRatio = `${w} / ${h}`;
  }

  $("compare").addEventListener("change", async () => {
    compareOn = $("compare").checked;
    if (compareOn && selectedFile && originalBitmap) {
      try {
        const fmt = $("fmt").value;
        const quality = Number($("q").value);
        const maxWidth = $("scale").checked ? Number($("sw").value) : 0;
        const { blob } = await runJob("convert_image", {
          file: selectedFile.file,
          opts: { format: fmt, quality, maxWidth },
        });
        if (pageToken !== getRenderToken()) return;
        if (processedBitmap) processedBitmap.close();
        processedBitmap = await loadImageBitmap(blob);
      } catch {
        compareOn = false;
        $("compare").checked = false;
      }
    }
    drawPreview();
  });

  let dragging = false;
  const handle = $("compareHandle");
  handle.addEventListener("pointerdown", (ev) => {
    dragging = true;
    handle.setPointerCapture(ev.pointerId);
  });
  handle.addEventListener("pointermove", (ev) => {
    if (!dragging) return;
    const stage = $("stage");
    const r = stage.getBoundingClientRect();
    const x = Math.max(0, Math.min(r.width, ev.clientX - r.left));
    const canvas = $("previewCanvas");
    const split = Math.round((x / r.width) * canvas.width);
    handle.style.left = `${x}px`;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, split, h);
    ctx.clip();
    ctx.drawImage(originalBitmap, 0, 0, w, h);
    ctx.restore();
    ctx.save();
    ctx.beginPath();
    ctx.rect(split, 0, w - split, h);
    ctx.clip();
    ctx.drawImage(processedBitmap, 0, 0, w, h);
    ctx.restore();
  });
  handle.addEventListener("pointerup", () => {
    dragging = false;
  });

  window.addEventListener("resize", () => drawPreview());

  $("q").addEventListener("input", () => ($("qv").textContent = $("q").value));
  $("fmt").addEventListener("change", () => {
    try {
      localStorage.setItem("wc.fmt", $("fmt").value);
    } catch { /* ignore */ }
  });
  $("q").addEventListener("change", () => {
    try {
      localStorage.setItem("wc.q", $("q").value);
    } catch { /* ignore */ }
  });
  $("wm_size").addEventListener("input", () => ($("wm_size_v").textContent = $("wm_size").value));
  $("wm_opacity").addEventListener("input", () => ($("wm_opacity_v").textContent = `${$("wm_opacity").value}%`));
  $("wm_scale").addEventListener("input", () => ($("wm_scale_v").textContent = `${$("wm_scale").value}%`));
  $("wmtext").addEventListener("click", () => {
    $("wmtext").classList.add("active");
    $("wmimg").classList.remove("active");
    $("wm_text_field").hidden = false;
    $("wm_scale_field").hidden = true;
  });
  $("wmimg").addEventListener("click", () => {
    $("markfile").click();
  });
  let markFile = null;
  $("markfile").addEventListener("change", () => {
    markFile = $("markfile").files[0] || null;
    $("markfile").value = "";
    if (markFile) {
      $("wmimg").classList.add("active");
      $("wmtext").classList.remove("active");
      $("wm_text_field").hidden = true;
      $("wm_scale_field").hidden = false;
    }
  });
  $("scale").addEventListener("change", () => {
    $("sw").disabled = !$("scale").checked;
  });

  function stale() {
    return pageToken !== getRenderToken();
  }

  function addOutput(blob, filename) {
    if (stale()) return;
    const at = outputs.findIndex((o) => o.filename === filename);
    if (at >= 0) outputs.splice(at, 1);
    outputs.push({ blob, filename });
    $("zip").textContent = outputs.length > 1 ? `打包下载 ZIP（${outputs.length}）` : "打包下载 ZIP";
    syncSaveDir();
  }

  async function runOne(file, opts) {
    if (jobs.cancelled) throw new AppError("图片处理失败", "已取消");
    const { blob, filename } = await runJob("convert_image", { file, opts });
    addOutput(blob, filename);
    return filename;
  }

  $("start").addEventListener("click", async () => {
    if (addingPromise) await addingPromise;
    if (running || zipping) return;
    err.textContent = "";
    const files = fileEntries.map((e) => e.file);
    if (!files.length) {
      err.textContent = "请先添加图片文件";
      return;
    }
    for (const f of files) {
      try {
        await validateImageFile(f);
      } catch (e) {
        err.textContent = friendlyError(e);
        return;
      }
    }
    const fmt = $("fmt").value;
    const quality = Number($("q").value);
    const maxWidth = $("scale").checked ? Number($("sw").value) : 0;
    lastBatch = { files: [...files], fmt, quality, maxWidth };
    saveSettings({ imageFormat: fmt, imageQuality: quality, ...(maxWidth ? { imageWidth: maxWidth } : {}) });
    running = true;
    setTaskRunning(true);
    const t0 = trackStart();
    $("start").disabled = true;
    $("zip").disabled = true;
    try {
      jobs.submit(files.map((f, i) => ({ id: i, name: f.name, thumb: URL.createObjectURL(f) })));
      // 2 路流水线:池的两个 worker 同时吃任务;取消后不再派发新文件
      const results = await runLimited(
        files.length,
        async (i) => {
          const entry = fileEntries[i];
          jobs.setStatus(i, "running");
          setFileStatus(entry, "running");
          jobs.setProgress(batchPct(i, 0, files.length));
          jobs.setBatch(i, files.length, files[i].name);
          try {
            await runOne(files[i], { format: fmt, quality, maxWidth });
            jobs.setStatus(i, "done");
            setFileStatus(entry, "done");
            jobs.setProgress(batchPct(i, 100, files.length));
          } catch (e) {
            trackFailure(e);
            const msg = friendlyError(e);
            const cancelled = msg.includes("已取消");
            jobs.setStatus(i, cancelled ? "cancelled" : "failed", msg);
            setFileStatus(entry, cancelled ? "cancelled" : "failed");
          }
        },
        { limit: 2, shouldStop: () => jobs.cancelled },
      );
      // 未派发的文件(取消后)标记取消,与串行版 break 行为一致
      for (let i = 0; i < files.length; i++) {
        if (!results[i]) {
          jobs.setStatus(i, "cancelled", "已取消");
          setFileStatus(fileEntries[i], "cancelled");
        }
      }
      jobs.finish();
      if (!stale()) {
        if (outputs.length) showToast(`转换完成，共 ${outputs.length} 个文件`, "success");
        const failed = fileEntries.filter((e) => e.status === "failed").length;
        $("retry").hidden = failed === 0;
      }
    } finally {
      running = false;
      setTaskRunning(false);
      trackEnd(t0);
      if (!stale()) {
        $("start").disabled = false;
        $("zip").disabled = false;
      }
    }
  });

  $("retry").addEventListener("click", async () => {
    if (!lastBatch || running) return;
    const failedIdx = fileEntries
      .map((e, i) => (e.status === "failed" ? i : -1))
      .filter((i) => i >= 0);
    if (!failedIdx.length) return;
    running = true;
    setTaskRunning(true);
    const t0 = trackStart();
    $("start").disabled = true;
    $("retry").disabled = true;
    try {
      for (const i of failedIdx) {
        if (stale() || jobs.cancelled) break;
        const entry = fileEntries[i];
        jobs.setStatus(i, "running");
        setFileStatus(entry, "running");
        jobs.setBatch(i, lastBatch.files.length, lastBatch.files[i].name);
        try {
          await runOne(lastBatch.files[i], {
            format: lastBatch.fmt,
            quality: lastBatch.quality,
            maxWidth: lastBatch.maxWidth,
          });
          jobs.setStatus(i, "done");
          setFileStatus(entry, "done");
        } catch (e) {
          trackFailure(e);
          const msg = friendlyError(e);
          jobs.setStatus(i, "failed", msg);
          setFileStatus(entry, "failed");
        }
      }
      jobs.finish();
    } finally {
      running = false;
      setTaskRunning(false);
      trackEnd(t0);
      if (!stale()) {
        $("start").disabled = false;
        $("retry").disabled = false;
      }
    }
  });

  $("zip").addEventListener("click", async () => {
    if (running || zipping) return;
    err.textContent = "";
    if (!outputs.length) {
      err.textContent = "还没有可下载的输出";
      return;
    }
    zipping = true;
    $("zip").disabled = true;
    try {
      await ensureJszip();
      const zip = new globalThis.JSZip();
      for (const o of outputs) zip.file(o.filename, o.blob);
      jobs.setZipProgress(0, "images.zip");
      const blob = await zip.generateAsync({ type: "blob" }, (meta) =>
        jobs.setZipProgress(meta.percent, "images.zip")
      );
      downloadBlob(blob, "images.zip");
    } catch (e) {
      err.textContent = friendlyError(e);
    } finally {
      zipping = false;
      $("zip").disabled = false;
    }
  });

  $("savedir").addEventListener("click", async () => {
    if (running || zipping || saving || !outputs.length) return;
    err.textContent = "";
    saving = true;
    $("savedir").disabled = true;
    try {
      const dir = await pickOutputDirectory();
      const written = await saveBlobsToDirectory(dir, outputs);
      setStatus(`已保存 ${written.length} 个文件到所选文件夹`);
    } catch (e) {
      if (!(e instanceof AppError && e.detail === "已取消选择")) {
        err.textContent = friendlyError(e);
      }
    } finally {
      saving = false;
      $("savedir").disabled = false;
    }
  });

  $("crop").addEventListener("click", async () => {
    err.textContent = "";
    let bitmap = null;
    try {
      const f = selectedFile ? selectedFile.file : fileEntries[0]?.file;
      if (!f) throw new AppError("图片处理失败", "请先添加图片文件");
      bitmap = await loadImageBitmap(f);
      const box = await pickBoxOnPage(bitmap);
      if (!box) return;
      const canvas = cropCanvas(bitmap, box);
      const blob = await new Promise((res, rej) =>
        canvas.toBlob((b) => (b ? res(b) : rej(new AppError("图片处理失败", "保存失败"))), "image/png")
      );
      const filename = `${stem(f.name)}_crop.png`;
      addOutput(blob, filename);
      downloadBlob(blob, filename);
    } catch (e) {
      err.textContent = friendlyError(e);
    } finally {
      bitmap && bitmap.close && bitmap.close();
    }
  });

  const POSITION_LABELS = [
    ["bottom_right", "右下"],
    ["bottom_left", "左下"],
    ["top_right", "右上"],
    ["top_left", "左上"],
    ["center", "居中"],
  ];

  function syncWatermarkKind() {
    const textMode = $("wmtext").classList.contains("active");
    $("wm_text_field").hidden = !textMode;
    $("wm_scale_field").hidden = textMode;
  }

  $("wm_apply").addEventListener("click", async () => {
    if (running) return;
    err.textContent = "";
    const files = fileEntries.map((e) => e.file);
    if (!files.length) {
      err.textContent = "请先添加图片文件";
      return;
    }
    for (const f of files) {
      try {
        await validateImageFile(f);
      } catch (e) {
        err.textContent = friendlyError(e);
        return;
      }
    }
    const position = $("wm_pos").value;
    const opacity = Number($("wm_opacity").value) / 100;
    const textMode = $("wmtext").classList.contains("active");
    const text = $("wm_text").value.trim();
    const fontSize = Number($("wm_size").value);
    const scale = Number($("wm_scale").value) / 100;
    if (textMode && !text) {
      err.textContent = "请输入水印文字";
      return;
    }
    const mark = textMode ? null : markFile;
    if (!textMode && !mark) {
      err.textContent = "请先选择水印图片";
      return;
    }
    running = true;
    $("wm_apply").disabled = true;
    try {
      jobs.submit(files.map((f, i) => ({ id: i, name: f.name, thumb: URL.createObjectURL(f) })));
      const produced = [];
      for (let i = 0; i < files.length; i++) {
        if (jobs.cancelled) {
          jobs.setStatus(i, "cancelled", "已取消");
          continue;
        }
        jobs.setStatus(i, "running");
        jobs.setProgress(batchPct(i, 0, files.length));
        jobs.setBatch(i, files.length, files[i].name);
        try {
          const res = textMode
            ? await runJob("text_watermark", { file: files[i], opts: { text, fontSize, position, color: `rgba(255,255,255,${opacity})` } })
            : await runJob("image_watermark", { file: files[i], mark, opts: { scale, opacity, position } });
          addOutput(res.blob, res.filename);
          produced.push({ blob: res.blob, filename: res.filename });
          jobs.setStatus(i, "done");
          jobs.setProgress(batchPct(i, 100, files.length));
        } catch (e) {
          const msg = friendlyError(e);
          jobs.setStatus(i, msg.includes("已取消") ? "cancelled" : "failed", msg);
        }
      }
      jobs.finish();
      if (!stale() && produced.length === 1) {
        downloadBlob(produced[0].blob, produced[0].filename);
      }
    } finally {
      running = false;
      if (!stale()) {
        $("wm_apply").disabled = false;
      }
    }
  });

  async function ensureJszip() {
    if (globalThis.JSZip) return;
    try {
      await loadScriptFirstOnce(JSZIP_URLS);
    } catch {
      throw new AppError("图片处理失败", `无法加载依赖: ${JSZIP_URLS.join(" / ")}`);
    }
    if (!globalThis.JSZip) throw new AppError("图片处理失败", "JSZip 加载失败");
  }

  function pickBoxOnPage(bitmap) {
    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:50;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:8px";
      const canvas = document.createElement("canvas");
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
        try {
          if (ev.pointerId != null && canvas.setPointerCapture) canvas.setPointerCapture(ev.pointerId);
        } catch { /* pointer already gone */ }
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
}
