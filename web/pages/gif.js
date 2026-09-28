// web/pages/gif.js
import { mergeGif, splitGif, loadGifFrames, gifFrameStats, gifSplitTooLarge } from "../lib/gif_ops.js";
import { createJobList } from "../lib/joblist.js";
import { batchPct } from "../lib/progress.js";
import { validateSelection } from "../lib/selection.js";
import { JSZIP_URLS, loadScriptFirstOnce } from "../lib/cdn.js";
import { downloadBlob, supportsFileSystemAccess, pickOutputDirectory, saveBlobsToDirectory } from "../lib/download.js";
import { friendlyError, AppError } from "../lib/errors.js";
import { validateImageFile } from "../lib/validate.js";
import { setStatus } from "../app.js";
import { registerShortcutAction } from "../lib/shortcuts.js";
import { showToast } from "../lib/toast.js";
import { loadSettings, saveSettings } from "../lib/settings.js";
import { runJob } from "../lib/worker_client.js";
import { getRenderToken, setTaskRunning } from "../app.js";
import { trackEnd, trackFailure, trackStart, trackUpload } from "../lib/track.js";
import { reportJob } from "../lib/jobcenter.js";

const IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"];
const PLAYER_FPS = 10;

export function mountGif(root) {
  root.innerHTML = `
    <div class="page-head">
      <h1>GIF 工具</h1>
      <p>拆帧按 delta 与 disposal 正确合成；合帧逐帧编码。左侧文件，中间播放器/预览，右侧参数。</p>
    </div>
    <div class="gif-layout">
      <aside class="img-files">
        <div class="img-files-head">
          <span>文件</span>
          <button type="button" class="btn secondary" id="addFiles">添加</button>
          <input type="file" id="files" multiple accept="image/*,.gif" hidden />
        </div>
        <div class="img-file-list" id="fileList"></div>
      </aside>
      <div class="gif-preview">
        <div class="preview-stage" id="stage">
          <canvas id="gifCanvas"></canvas>
          <div class="preview-empty" id="previewEmpty">选择左侧文件预览</div>
        </div>
        <div class="gif-player-bar" id="playerBar" hidden>
          <button type="button" class="btn secondary" id="playBtn">▶ 播放</button>
          <select id="speed" class="gif-speed">
            <option value="0.25">0.25x</option>
            <option value="0.5">0.5x</option>
            <option value="1" selected>1x</option>
            <option value="2">2x</option>
          </select>
          <input type="range" id="gifTimeline" min="0" max="0" value="0" />
          <span class="preview-info" id="gifFrameInfo"></span>
        </div>
        <div class="gif-gallery" id="gallery" hidden>
          <p class="panel-title">拆帧结果</p>
          <div class="gallery-grid" id="galleryGrid"></div>
        </div>
      </div>
      <div class="gif-params">
        <div class="panel">
          <p class="panel-title">模式与参数</p>
          <div class="row">
            <div class="field">
              <label for="mode">模式</label>
              <select id="mode">
                <option value="split">拆帧（GIF → PNG 序列）</option>
                <option value="merge">合帧（图片 → GIF）</option>
              </select>
            </div>
            <div class="field" id="wstep">
              <label for="step">抽稀步长</label>
              <input type="number" id="step" min="1" max="30" value="1" />
            </div>
            <div class="field" id="wdur">
              <label for="dur">帧率 <span id="dur_v">30</span> FPS</label>
              <input type="range" id="dur" min="1" max="60" value="30" />
            </div>
            <div class="field" id="wrev" hidden>
              <label class="inline"><input type="checkbox" id="rev" /> 倒放</label>
            </div>
            <div class="field" id="wloop" hidden>
              <label for="loop">循环</label>
              <select id="loop">
                <option value="0">无限循环</option>
                <option value="1">播放一次</option>
                <option value="2">2 次</option>
                <option value="3">3 次</option>
              </select>
            </div>
            <div class="field" id="wcolors" hidden>
              <label for="colors">色彩数</label>
              <select id="colors">
                <option value="256">256 色</option>
                <option value="128">128 色</option>
                <option value="64">64 色</option>
              </select>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="img-actionbar">
      <button type="button" class="btn" id="start">开始</button>
      <button type="button" class="btn secondary" id="retry" hidden>重试失败</button>
      <button type="button" class="btn secondary" id="zip" hidden>打包下载 ZIP</button>
      <button type="button" class="btn secondary" id="savedir" hidden>保存到文件夹</button>
      <span class="actionbar-pct" id="actionbarPct"></span>
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
    onReport: (job) => reportJob({ ...job, id: `gif:${job.id}`, page: "GIF" }),
  });
  let splitFiles = [];
  let lastSplit = null;
  let running = false;
  let zipping = false;
  let saving = false;
  let selectedFile = null;
  let playerFrames = [];
  let playerIdx = 0;
  let playerPlaying = false;
  let playerTimer = null;
  const pageToken = getRenderToken();

  registerShortcutAction("onOpen", () => $("files").click());
  registerShortcutAction("onStart", () => {
    if (!running) $("start").click();
  });
  registerShortcutAction("onDownload", () => {
    if (splitFiles.length) $("zip").click();
  });
  registerShortcutAction("onCancel", () => {
    const btn = root.querySelector('[data-act="cancel"]');
    if (btn && !btn.disabled) btn.click();
  });

  const settings = loadSettings();
  $("step").value = String(settings.gifStep);

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
      const check = validateSelection([f], { extensions: IMAGE_EXTS });
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

  async function selectFile(entry) {
    selectedFile = entry;
    renderFileList();
    stopPlayer();
    playerFrames = [];
    $("gifTimeline").value = "0";
    $("gifFrameInfo").textContent = "";
    const split = $("mode").value === "split";
    if (split && entry.file.name.toLowerCase().endsWith(".gif")) {
    try {
      const { frames } = await loadGifFrames(entry.file, { token });
      if (pageToken !== getRenderToken()) return;
      playerFrames = frames;
        $("previewEmpty").hidden = true;
        $("playerBar").hidden = false;
        $("gifTimeline").max = String(Math.max(0, frames.length - 1));
        playerIdx = 0;
        drawPlayerFrame();
      } catch (e) {
        $("err").textContent = friendlyError(e);
        $("playerBar").hidden = true;
      }
    } else {
      $("playerBar").hidden = true;
      $("previewEmpty").hidden = false;
    }
  }

  function drawPlayerFrame() {
    const canvas = $("gifCanvas");
    if (!canvas || !playerFrames.length) return;
    const frame = playerFrames[playerIdx];
    canvas.width = frame.width;
    canvas.height = frame.height;
    canvas.getContext("2d").drawImage(frame, 0, 0);
    $("gifFrameInfo").textContent = `帧 ${playerIdx + 1} / ${playerFrames.length}`;
    $("gifTimeline").value = String(playerIdx);
  }

  function playerTick() {
    if (pageToken !== getRenderToken()) {
      stopPlayer();
      return;
    }
    if (!playerPlaying || !playerFrames.length) return;
    playerIdx = (playerIdx + 1) % playerFrames.length;
    drawPlayerFrame();
    const speed = Number($("speed").value) || 1;
    playerTimer = setTimeout(playerTick, 1000 / (PLAYER_FPS * speed));
  }

  function stopPlayer() {
    playerPlaying = false;
    if (playerTimer) clearTimeout(playerTimer);
    playerTimer = null;
    const btn = $("playBtn");
    if (btn) btn.textContent = "▶ 播放";
  }

  $("playBtn").addEventListener("click", () => {
    if (!playerFrames.length) return;
    playerPlaying = !playerPlaying;
    $("playBtn").textContent = playerPlaying ? "⏸ 暂停" : "▶ 播放";
    if (playerPlaying) playerTick();
    else if (playerTimer) clearTimeout(playerTimer);
  });
  $("speed").addEventListener("change", () => {
    if (playerPlaying) {
      if (playerTimer) clearTimeout(playerTimer);
      playerTick();
    }
  });
  $("gifTimeline").addEventListener("input", () => {
    playerIdx = Number($("gifTimeline").value) || 0;
    drawPlayerFrame();
  });

  function syncMode() {
    const split = $("mode").value === "split";
    $("wstep").hidden = !split;
    $("wdur").hidden = split;
    $("wrev").hidden = split;
    $("wloop").hidden = split;
    $("wcolors").hidden = split;
    $("zip").hidden = !split;
    $("start").textContent = split ? "开始拆帧" : "开始合帧";
    $("files").accept = split ? ".gif,image/gif" : "image/*,.gif";
    $("retry").hidden = true;
    if (selectedFile) selectFile(selectedFile);
  }
  $("mode").addEventListener("change", syncMode);
  $("dur").addEventListener("input", () => ($("dur_v").textContent = $("dur").value));
  syncMode();

  function syncSaveDir() {
    const btn = $("savedir");
    if (btn) btn.hidden = !supportsFileSystemAccess() || splitFiles.length === 0;
  }

  function renderGallery() {
    const grid = $("galleryGrid");
    grid.innerHTML = "";
    splitFiles.forEach((f) => {
      const img = document.createElement("img");
      img.src = URL.createObjectURL(f.blob);
      img.alt = f.name;
      img.title = f.name;
      img.className = "gallery-item";
      grid.appendChild(img);
    });
    $("gallery").hidden = splitFiles.length === 0;
  }

  function stale() {
    return pageToken !== getRenderToken();
  }

  $("start").addEventListener("click", async () => {
    if (running) return;
    const err = $("err");
    err.textContent = "";
    token.cancelled = false;
    const files = fileEntries.map((e) => e.file);
    if (!files.length) {
      err.textContent = $("mode").value === "split" ? "请先添加 GIF 文件" : "请先添加图片序列";
      return;
    }
    const wanted = $("mode").value === "split" ? [".gif"] : IMAGE_EXTS;
    const check = validateSelection(files, { extensions: wanted });
    if (!check.ok) {
      err.textContent = check.errors.map((e) => `${e.name}：${e.reason}`).join("\n");
      return;
    }
    const accepted = check.files;
    if ($("mode").value === "split" && Number($("step").value) >= 1) {
      saveSettings({ gifStep: Number($("step").value) });
    }
    running = true;
    setTaskRunning(true);
    const t0 = trackStart();
    $("start").disabled = true;
    $("zip").disabled = true;
    try {
      if ($("mode").value === "split") {
        // hard limit: reject huge GIFs before decoding every frame
        for (const f of accepted) {
          try {
            const stats = await gifFrameStats(f);
            if (gifSplitTooLarge(stats)) {
              err.textContent = `该 GIF 总像素过高（${stats.width}×${stats.height}×${stats.frameCount} 帧 ≈ ${Math.round(stats.totalPixels / 1e6)}MP），Web 端处理可能崩溃。建议使用桌面版。`;
              return;
            }
          } catch {
            // stats unavailable; normal processing will surface the error
          }
        }
        jobs.submit(accepted.map((f, i) => ({ id: i, name: f.name, thumb: URL.createObjectURL(f) })));
        splitFiles = [];
        lastSplit = accepted;
        for (let i = 0; i < accepted.length; i++) {
          if (stale()) return;
          if (jobs.cancelled) {
            jobs.setStatus(i, "cancelled", "已取消");
            continue;
          }
          jobs.setStatus(i, "running");
          jobs.setProgress(batchPct(i, 0, accepted.length));
          jobs.setBatch(i, accepted.length, accepted[i].name);
          try {
            const { files: parts } = await runJob(
              "gif_split",
              {
                file: accepted[i],
                opts: { step: Number($("step").value) },
              },
              {
                onProgress: (done, total) =>
                  jobs.setProgress(
                    batchPct(i, total ? (done / total) * 100 : 0, accepted.length)
                  ),
              },
            );
            if (stale()) return;
            splitFiles.push(...parts);
            jobs.setStatus(i, "done");
            jobs.setProgress(batchPct(i, 100, accepted.length));
            renderGallery();
            syncSaveDir();
          } catch (e) {
            trackFailure(e);
            const msg = friendlyError(e);
            const cancelled = msg.includes("已取消");
            jobs.setStatus(i, cancelled ? "cancelled" : "failed", msg);
            if (cancelled) continue;
          }
        }
        jobs.finish();
        if (!stale()) {
          $("retry").hidden = jobs.failedIndices().length === 0;
          if (splitFiles.length) showToast(`拆帧完成，共 ${splitFiles.length} 帧`, "success");
        }
        return;
      }
      // merge
      const ordered = [...accepted].sort((a, b) => a.name.localeCompare(b.name));
      jobs.submit([{ id: 0, name: ordered[0].name, thumb: URL.createObjectURL(ordered[0]) }]);
      jobs.setStatus(0, "running");
      try {
        const fps = Number($("dur").value) || 30;
        const { blob, filename } = await runJob("gif_merge", {
          files: ordered,
          opts: {
            durationMs: Math.round(1000 / fps),
            loop: Number($("loop").value),
            reverse: $("rev").checked,
            colors: Number($("colors").value),
          },
        });
        jobs.setStatus(0, "done");
        downloadBlob(blob, filename);
        showToast("合帧完成", "success");
      } catch (e) {
        trackFailure(e);
        const msg = friendlyError(e);
        const cancelled = msg.includes("已取消");
        jobs.setStatus(0, cancelled ? "cancelled" : "failed", msg);
      }
      jobs.finish();
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
    if (!lastSplit || running || zipping) return;
    const failedIdx = jobs.failedIndices();
    if (!failedIdx.length) return;
    token.cancelled = false;
    running = true;
    setTaskRunning(true);
    const t0 = trackStart();
    $("start").disabled = true;
    $("zip").disabled = true;
    $("retry").disabled = true;
    try {
      for (const i of failedIdx) {
        if (stale()) return;
        if (jobs.cancelled) {
          jobs.setStatus(i, "cancelled", "已取消");
          continue;
        }
        jobs.setStatus(i, "running");
        jobs.setProgress(batchPct(i, 0, lastSplit.length));
        jobs.setBatch(i, lastSplit.length, lastSplit[i].name);
        try {
          const { files: parts } = await runJob(
            "gif_split",
            {
              file: lastSplit[i],
              opts: { step: Number($("step").value) },
            },
            {
              onProgress: (done, total) =>
                jobs.setProgress(
                  batchPct(i, total ? (done / total) * 100 : 0, lastSplit.length)
                ),
            },
          );
          if (stale()) return;
          splitFiles.push(...parts);
          jobs.setStatus(i, "done");
          jobs.setProgress(batchPct(i, 100, lastSplit.length));
          renderGallery();
          syncSaveDir();
        } catch (e) {
          trackFailure(e);
          const msg = friendlyError(e);
          const cancelled = msg.includes("已取消");
          jobs.setStatus(i, cancelled ? "cancelled" : "failed", msg);
          if (cancelled) continue;
        }
      }
      jobs.finish();
      if (!stale()) {
        $("retry").hidden = jobs.failedIndices().length === 0;
        if (splitFiles.length) showToast(`拆帧完成，共 ${splitFiles.length} 帧`, "success");
      }
    } finally {
      running = false;
      setTaskRunning(false);
      trackEnd(t0);
      if (!stale()) {
        $("start").disabled = false;
        $("zip").disabled = false;
        $("retry").disabled = false;
      }
    }
  });

  $("zip").addEventListener("click", async () => {
    if (running) return;
    try {
      if (!splitFiles.length) {
        $("err").textContent = "还没有拆帧结果";
        return;
      }
      await ensureJszipGif();
      const zip = new globalThis.JSZip();
      for (const f of splitFiles) zip.file(f.name, f.blob);
      jobs.setZipProgress(0, "frames.zip");
      const blob = await zip.generateAsync({ type: "blob" }, (meta) =>
        jobs.setZipProgress(meta.percent, "frames.zip")
      );
      downloadBlob(blob, "frames.zip");
    } catch (e) {
      $("err").textContent = friendlyError(e);
    }
  });

  $("savedir").addEventListener("click", async () => {
    if (running || zipping || saving || !splitFiles.length) return;
    saving = true;
    $("savedir").disabled = true;
    try {
      const dir = await pickOutputDirectory();
      const written = await saveBlobsToDirectory(dir, splitFiles);
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

  async function ensureJszipGif() {
    if (globalThis.JSZip) return;
    try {
      await loadScriptFirstOnce(JSZIP_URLS);
    } catch {
      throw new AppError("GIF 处理失败", `无法加载依赖: ${JSZIP_URLS.join(" / ")}`);
    }
    if (!globalThis.JSZip) throw new AppError("GIF 处理失败", "JSZip 加载失败");
  }
}
