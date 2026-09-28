// web/pages/video.js
import { assertVideoLimits, probeVideoDuration, durationTooLongError, MAX_VIDEO_BYTES, MAX_VIDEO_SECONDS } from "../lib/video_limits.js";
import { ensureFFmpeg, readFileToBlob, runFFmpeg, writeFileFromBlob } from "../lib/video_bridge.js";
import { validateVideoFile } from "../lib/validate.js";
import { validateSelection } from "../lib/selection.js";
import { createJobList } from "../lib/joblist.js";
import { batchPct } from "../lib/progress.js";
import { JSZIP_URLS, loadScriptFirstOnce } from "../lib/cdn.js";
import { downloadBlob, stem, supportsFileSystemAccess, pickOutputDirectory, saveBlobsToDirectory } from "../lib/download.js";
import { friendlyError, AppError } from "../lib/errors.js";
import { detectMobile, mobileScaleArgs, MOBILE_MAX_VIDEO_WIDTH, MOBILE_VIDEO_NOTE } from "../lib/mobile.js";
import { setStatus, getRenderToken, setTaskRunning } from "../app.js";
import { trackEnd, trackFailure, trackStart, trackUpload } from "../lib/track.js";
import { registerShortcutAction } from "../lib/shortcuts.js";
import { showToast } from "../lib/toast.js";
import { loadSettings, saveSettings } from "../lib/settings.js";
import { showErrorModal } from "../lib/errors-ui.js";
import { reportJob } from "../lib/jobcenter.js";

export function mountVideo(root) {
  root.innerHTML = `
    <div class="page-head">
      <h1>视频</h1>
      <p>格式互转、转 GIF、截取片段与帧率码率调整。左侧文件，中间播放器，右侧参数。</p>
    </div>
    <div class="gif-layout">
      <aside class="img-files">
        <div class="img-files-head">
          <span>文件</span>
          <button type="button" class="btn secondary" id="addFiles">添加</button>
          <input type="file" id="files" multiple accept="video/*,.mp4,.webm,.mov,.mkv" hidden />
        </div>
        <div class="img-file-list" id="fileList"></div>
      </aside>
      <div class="video-preview">
        <div class="preview-stage" id="stage">
          <video id="videoEl" controls></video>
          <div class="preview-empty" id="previewEmpty">选择左侧文件预览</div>
        </div>
        <div class="video-timeline" id="timeline">
          <div class="timeline-track">
            <div class="timeline-fill" id="timelineFill"></div>
            <div class="timeline-marker in" id="markerIn" hidden></div>
            <div class="timeline-marker out" id="markerOut" hidden></div>
            <div class="timeline-playhead" id="playhead"></div>
          </div>
          <div class="video-controls">
            <button type="button" class="btn secondary" id="playBtn">▶</button>
            <span class="preview-info" id="timeInfo">00:00 / 00:00</span>
          </div>
        </div>
        <div class="engine-loading" id="engineLoading" hidden>
          <span class="spinner"></span>
          <span id="engineText">引擎加载中…</span>
        </div>
        <div class="output-estimate" id="outputEstimate" hidden>
          <p class="panel-title">输出预估</p>
          <div id="estimateBody"></div>
        </div>
      </div>
      <div class="gif-params">
        <div class="panel">
          <p class="panel-title">模式与参数</p>
          <div class="row">
            <div class="field">
              <label for="mode">模式</label>
              <select id="mode">
                <option value="convert">格式互转</option>
                <option value="gif">视频转 GIF</option>
                <option value="frames">截取帧</option>
                <option value="trim">片段截取</option>
              </select>
            </div>
            <div class="field" id="fmtw">
              <label for="fmt">输出格式</label>
              <select id="fmt">
                <option value="mp4">MP4</option>
                <option value="webm">WebM</option>
              </select>
            </div>
            <div class="field" id="gifw" hidden>
              <label for="gw">宽度</label>
              <input type="number" id="gw" min="16" max="3840" value="480" />
            </div>
            <div class="field" id="everyw" hidden>
              <label for="every">每 N 秒</label>
              <input type="number" id="every" min="0.1" step="0.1" value="1" />
            </div>
            <div class="field" id="trimw" hidden>
              <label for="t0">起 (s) / 止 (s)</label>
              <span class="row">
                <input type="number" id="t0" min="0" step="0.1" value="0" />
                <input type="number" id="t1" min="0.1" step="0.1" value="5" />
              </span>
            </div>
          </div>
          <div class="row" id="converw" hidden>
            <div class="field">
              <label for="crf">CRF <span id="crf_v">23</span></label>
              <input type="range" id="crf" min="0" max="51" value="23" />
            </div>
            <div class="field">
              <label for="tfps">目标帧率 <span id="tfps_v">不转换</span></label>
              <input type="number" id="tfps" min="0" max="120" value="0" />
            </div>
            <div class="field">
              <label class="inline"><input type="checkbox" id="mci" /> 运动补偿插帧</label>
            </div>
            <div class="field">
              <label class="inline"><input type="checkbox" id="hdr" /> HDR 转 SDR</label>
            </div>
            <div class="field">
              <label class="inline"><input type="checkbox" id="audionorm" checked /> 音频规范化 48kHz 立体声</label>
            </div>
          </div>
          <div class="row" id="gifopts" hidden>
            <div class="field">
              <label for="gifFps">帧率</label>
              <input type="number" id="gifFps" min="1" max="50" value="15" />
            </div>
            <div class="field">
              <label for="gifColors">色彩数</label>
              <select id="gifColors">
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
      <button type="button" class="btn" id="start">开始转换</button>
      <button type="button" class="btn secondary" id="retry" hidden>重试失败</button>
      <button type="button" class="btn secondary" id="zip" disabled>打包下载 ZIP</button>
      <button type="button" class="btn secondary" id="savedir" hidden>保存到文件夹</button>
      <span class="actionbar-pct" id="actionbarPct"></span>
    </div>
    <div id="jobs"></div>
    <pre class="err" id="err"></pre>
  `;
  const $ = (id) => root.querySelector(`#${id}`);
  const token = { cancelled: false };
  const jobs = createJobList(root.querySelector("#jobs"), {
    onReport: (job) => reportJob({ ...job, id: `video:${job.id}`, page: "视频" }),
  });
  let running = false;
  let zipping = false;
  let saving = false;
  const outputs = [];
  let selectedFile = null;
  let videoDuration = 0;
  const pageToken = getRenderToken();

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
  if ([...$("fmt").options].some((o) => o.value === settings.videoFormat)) {
    $("fmt").value = settings.videoFormat;
  }
  $("crf").value = String(settings.videoCrf);
  $("crf_v").textContent = String(settings.videoCrf);

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
      const check = validateSelection([f], { extensions: [".mp4", ".webm", ".mov", ".mkv"] });
      if (!check.ok) {
        $("err").textContent = check.errors.map((e) => `${e.name}：${e.reason}`).join("\n");
        continue;
      }
      try {
        assertVideoLimits(f);
      } catch (e) {
        $("err").textContent = friendlyError(e);
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
    const url = URL.createObjectURL(entry.file);
    const video = $("videoEl");
    video.src = url;
    $("previewEmpty").hidden = true;
    video.addEventListener("loadedmetadata", () => {
      if (pageToken !== getRenderToken()) return;
      videoDuration = video.duration || 0;
      updateTime();
      if ($("mode").value === "trim") syncTrimMarkers();
    }, { once: true });
  }

  function fmtTime(sec) {
    if (!Number.isFinite(sec) || sec < 0) sec = 0;
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  function updateTime() {
    if (pageToken !== getRenderToken()) return;
    const video = $("videoEl");
    $("timeInfo").textContent = `${fmtTime(video.currentTime)} / ${fmtTime(videoDuration)}`;
    if (videoDuration > 0) {
      $("timelineFill").style.width = `${(video.currentTime / videoDuration) * 100}%`;
      $("playhead").style.left = `${(video.currentTime / videoDuration) * 100}%`;
    }
  }

  const video = $("videoEl");
  video.addEventListener("timeupdate", updateTime);
  video.addEventListener("ended", () => {
    $("playBtn").textContent = "▶";
  });
  $("playBtn").addEventListener("click", () => {
    if (video.paused) {
      video.play();
      $("playBtn").textContent = "⏸";
    } else {
      video.pause();
      $("playBtn").textContent = "▶";
    }
  });

  function syncTrimMarkers() {
    const t0 = Number($("t0").value) || 0;
    const t1 = Math.max(t0 + 0.1, Number($("t1").value) || t0 + 0.1);
    if (videoDuration > 0) {
      $("markerIn").style.left = `${(t0 / videoDuration) * 100}%`;
      $("markerOut").style.left = `${(t1 / videoDuration) * 100}%`;
      $("markerIn").hidden = false;
      $("markerOut").hidden = false;
    }
  }

  function makeDraggable(marker, onChange) {
    marker.addEventListener("pointerdown", (ev) => {
      ev.preventDefault();
      marker.setPointerCapture(ev.pointerId);
      const move = (e) => {
        const track = $("timeline").querySelector(".timeline-track");
        const r = track.getBoundingClientRect();
        const pct = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
        marker.style.left = `${pct * 100}%`;
        onChange(pct * videoDuration);
      };
      const up = () => {
        marker.removeEventListener("pointermove", move);
        marker.removeEventListener("pointerup", up);
      };
      marker.addEventListener("pointermove", move);
      marker.addEventListener("pointerup", up);
    });
  }
  makeDraggable($("markerIn"), (t) => {
    $("t0").value = t.toFixed(1);
    const t1 = Math.max(t + 0.1, Number($("t1").value) || t + 0.1);
    $("t1").value = t1.toFixed(1);
  });
  makeDraggable($("markerOut"), (t) => {
    const t0 = Number($("t0").value) || 0;
    const v = Math.max(t0 + 0.1, t);
    $("t1").value = v.toFixed(1);
  });

  function syncMode() {
    const m = $("mode").value;
    $("fmtw").hidden = m !== "convert";
    $("converw").hidden = m !== "convert";
    $("gifw").hidden = m !== "gif";
    $("gifopts").hidden = m !== "gif";
    $("everyw").hidden = m !== "frames";
    $("trimw").hidden = m !== "trim";
    $("start").textContent =
      m === "convert" ? "开始转换" : m === "gif" ? "转 GIF" : m === "frames" ? "截取帧" : "片段截取";
    $("timeline").style.display = m === "trim" ? "block" : "block";
    if (m === "trim") syncTrimMarkers();
    updateEstimate();
  }
  $("mode").addEventListener("change", syncMode);
  $("t0").addEventListener("change", syncTrimMarkers);
  $("t1").addEventListener("change", syncTrimMarkers);
  $("crf").addEventListener("input", () => ($("crf_v").textContent = $("crf").value));
  $("tfps").addEventListener("input", () => {
    const v = Number($("tfps").value) || 0;
    $("tfps_v").textContent = v > 0 ? `${v}fps` : "不转换";
  });

  function updateEstimate() {
    const m = $("mode").value;
    const est = $("outputEstimate");
    if (!selectedFile || !videoDuration) {
      est.hidden = true;
      return;
    }
    const mb = (selectedFile.size || 0) / 1024 / 1024;
    let line = "";
    if (m === "convert") {
      const crf = Number($("crf").value);
      const ratio = crf <= 18 ? 0.7 : crf <= 23 ? 0.5 : 0.35;
      line = `格式 ${$("fmt").value.toUpperCase()} · 约 ${Math.max(1, Math.round(mb * ratio))}MB · 约 ${Math.max(1, Math.round(videoDuration * 2))}s`;
    } else if (m === "gif") {
      line = `GIF · 约 ${Math.max(1, Math.round(mb * 0.4))}MB`;
    } else if (m === "trim") {
      const t0 = Number($("t0").value) || 0;
      const t1 = Number($("t1").value) || t0;
      line = `截取 ${fmtTime(t0)} → ${fmtTime(t1)} · 约 ${Math.max(1, Math.round(mb * Math.max(0.1, (t1 - t0) / videoDuration)))}MB`;
    } else {
      line = `截帧 · 约 ${Math.max(1, Math.round(videoDuration / Number($("every").value)))} 张`;
    }
    $("estimateBody").innerHTML = `<div class="estimate-line">${line}</div>`;
    est.hidden = false;
  }
  $("mode").addEventListener("change", updateEstimate);
  $("crf").addEventListener("input", updateEstimate);
  $("tfps").addEventListener("input", updateEstimate);
  $("t0").addEventListener("change", updateEstimate);
  $("t1").addEventListener("change", updateEstimate);
  syncMode();

  function syncSaveDir() {
    const btn = $("savedir");
    if (btn) btn.hidden = !supportsFileSystemAccess() || outputs.length === 0;
  }

  function stale() {
    return pageToken !== getRenderToken();
  }

  async function processOne(file, mode, onPct) {
    await validateVideoFile(file);
    const ff = await ensureFFmpeg();
    const inName = `in_${file.name.replace(/[^\w.-]+/g, "_")}`;
    await writeFileFromBlob(ff, inName, file);
    const scratch = [inName];
    const base = stem(file.name);
    try {
      if (mode === "convert") {
        const ext = $("fmt").value;
        const out = `out.${ext}`;
        scratch.push(out);
        const scale = mobile ? mobileScaleArgs(MOBILE_MAX_VIDEO_WIDTH) : [];
        const vf = [];
        const fps = Number($("tfps").value) || 0;
        if (fps > 0) {
          vf.push(
            $("mci").checked
              ? `minterpolate='mi_mode=mci:mc_mode=aobmc:vsbmc=1:fps=${fps}'`
              : `fps=${fps}`,
          );
        }
        if ($("hdr").checked) {
          vf.push(
            "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p",
          );
        }
        const crf = Number($("crf").value);
        const audio = $("audionorm").checked;
        const args = ["-i", inName, ...scale];
        if (vf.length) args.push("-vf", vf.join(","));
        if (ext === "webm") {
          args.push("-c:v", "libvpx-vp9", "-crf", String(crf));
          if (audio) args.push("-c:a", "libopus", "-ar", "48000", "-ac", "2");
          else args.push("-an");
        } else {
          args.push("-c:v", "libx264", "-preset", "veryfast", "-crf", String(crf), "-pix_fmt", "yuv420p");
          if (audio) args.push("-c:a", "aac", "-ar", "48000", "-ac", "2");
        }
        args.push(out);
        await runFFmpeg({ args, outPath: out, onProgress: onPct, cancelToken: token });
        const blob = await readFileToBlob(ff, out);
        return { blob, filename: `${base}.${ext}` };
      } else if (mode === "gif") {
        const out = `${base}.gif`;
        scratch.push(out);
        const args = [
          "-i", inName, "-an",
          "-vf",
          `fps=${$("gifFps").value},scale=${$("gw").value}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=${$("gifColors").value}[p];[s1][p]paletteuse=dither=bayer`,
          out,
        ];
        await runFFmpeg({ args, outPath: out, onProgress: onPct, cancelToken: token });
        const blob = await readFileToBlob(ff, out);
        return { blob, filename: out };
      } else if (mode === "frames") {
        const pattern = `frame_%04d.png`;
        const args = ["-i", inName, "-vf", `fps=1/${$("every").value}`, pattern];
        await runFFmpeg({ args, outPath: pattern, onProgress: onPct, cancelToken: token });
        const names = await listFiles(ff, /frame_\d+\.png$/);
        scratch.push(...names);
        await ensureJszipV();
        const zip = new globalThis.JSZip();
        for (const n of names) zip.file(n, await readFileToBlob(ff, n));
        const zipBlob = await zip.generateAsync({ type: "blob" });
        return { blob: zipBlob, filename: `${base}_frames.zip` };
      } else {
        const out = `${base}_trim.mp4`;
        scratch.push(out);
        const t0 = Math.max(0, Number($("t0").value) || 0);
        const t1 = Math.max(t0 + 0.1, Number($("t1").value) || t0 + 0.1);
        const args = [
          "-ss", String(t0), "-i", inName, "-t", String(t1 - t0),
          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", out,
        ];
        await runFFmpeg({ args, outPath: out, onProgress: onPct, cancelToken: token });
        const blob = await readFileToBlob(ff, out);
        return { blob, filename: out };
      }
    } finally {
      for (const name of scratch) {
        try {
          await ff.deleteFile(name);
        } catch { /* already gone (e.g. after terminate) */ }
      }
    }
  }

  $("start").addEventListener("click", async () => {
    if (running) return;
    const err = $("err");
    err.textContent = "";
    token.cancelled = false;
    const files = fileEntries.map((e) => e.file);
    if (!files.length) {
      err.textContent = "请先添加视频文件";
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
    saveSettings({ videoFormat: $("fmt").value, videoCrf: Number($("crf").value) || 23 });
    running = true;
    setTaskRunning(true);
    const t0 = trackStart();
    $("start").disabled = true;
    try {
      const durations = await Promise.all(files.map((f) => probeVideoDuration(f)));
      for (const sec of durations) {
        if (sec != null && sec > MAX_VIDEO_SECONDS) {
          err.textContent = friendlyError(durationTooLongError());
          return;
        }
      }
      jobs.submit(files.map((f, i) => ({ id: i, name: f.name })));
      try {
        $("engineLoading").hidden = false;
        await ensureFFmpeg((msg) => {
          $("engineText").textContent = msg;
          setStatus(msg);
        });
        $("engineLoading").hidden = true;
      } catch (e) {
        $("engineLoading").hidden = true;
        showErrorModal({
          title: "视频引擎加载失败",
          body: `${friendlyError(e)}<br><br>请尝试：检查网络连接、使用最新版 Chrome / Edge、清除浏览器缓存后重试。`,
          actions: [
            { label: "重试", primary: true, onClick: () => location.reload() },
            { label: "使用桌面版", onClick: () => (location.hash = "#/desktop") },
          ],
        });
        jobs.finish();
        return;
      }
      for (let i = 0; i < files.length; i++) {
        if (stale() || token.cancelled || jobs.cancelled) {
          jobs.setStatus(i, "cancelled", "已取消");
          continue;
        }
        jobs.setStatus(i, "running");
        setFileStatus(fileEntries[i], "running");
        jobs.setBatch(i, files.length, files[i].name);
        try {
          const out = await processOne(files[i], $("mode").value, (p) =>
            jobs.setProgress(batchPct(i, p, files.length))
          );
          if (stale()) return;
          if (out) {
            outputs.push(out);
            jobs.setStatus(i, "done");
            setFileStatus(fileEntries[i], "done");
          } else {
            jobs.setStatus(i, "failed", "没有产出文件");
            setFileStatus(fileEntries[i], "failed");
          }
        } catch (e) {
          trackFailure(e);
          const msg = friendlyError(e);
          const cancelled = msg.includes("已取消");
          jobs.setStatus(i, cancelled ? "cancelled" : "failed", msg);
          setFileStatus(fileEntries[i], cancelled ? "cancelled" : "failed");
          if (cancelled) continue;
        }
      }
      jobs.finish();
      if (!stale() && outputs.length) showToast(`转换完成，共 ${outputs.length} 个文件`, "success");
      if (!stale()) {
        $("retry").hidden = jobs.failedIndices().length === 0;
        $("zip").disabled = outputs.length === 0;
        $("zip").textContent = outputs.length > 1 ? `打包下载 ZIP（${outputs.length}）` : "打包下载 ZIP";
        syncSaveDir();
      }
    } finally {
      running = false;
      setTaskRunning(false);
      trackEnd(t0);
      if (!stale()) {
        $("start").disabled = false;
      }
    }
  });

  $("retry").addEventListener("click", async () => {
    if (running) return;
    const failedIdx = jobs.failedIndices();
    if (!failedIdx.length) return;
    token.cancelled = false;
    running = true;
    setTaskRunning(true);
    const t0 = trackStart();
    $("start").disabled = true;
    $("retry").disabled = true;
    try {
      for (const i of failedIdx) {
        if (stale() || token.cancelled || jobs.cancelled) {
          jobs.setStatus(i, "cancelled", "已取消");
          setFileStatus(fileEntries[i], "cancelled");
          continue;
        }
        jobs.setStatus(i, "running");
        setFileStatus(fileEntries[i], "running");
        jobs.setBatch(i, fileEntries.length, fileEntries[i].file.name);
        try {
          const out = await processOne(fileEntries[i].file, $("mode").value, (p) =>
            jobs.setProgress(batchPct(i, p, fileEntries.length))
          );
          if (stale()) return;
          if (out) {
            outputs.push(out);
            jobs.setStatus(i, "done");
            setFileStatus(fileEntries[i], "done");
          } else {
            jobs.setStatus(i, "failed", "没有产出文件");
            setFileStatus(fileEntries[i], "failed");
          }
        } catch (e) {
          trackFailure(e);
          const msg = friendlyError(e);
          const cancelled = msg.includes("已取消");
          jobs.setStatus(i, cancelled ? "cancelled" : "failed", msg);
          setFileStatus(fileEntries[i], cancelled ? "cancelled" : "failed");
          if (cancelled) continue;
        }
      }
      jobs.finish();
      if (!stale()) {
        $("retry").hidden = jobs.failedIndices().length === 0;
        $("zip").disabled = outputs.length === 0;
        $("zip").textContent = outputs.length > 1 ? `打包下载 ZIP（${outputs.length}）` : "打包下载 ZIP";
        syncSaveDir();
      }
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
    if (zipping || !outputs.length) return;
    zipping = true;
    $("zip").disabled = true;
    try {
      await ensureJszipV();
      const zip = new globalThis.JSZip();
      for (const o of outputs) zip.file(o.filename, o.blob);
      jobs.setZipProgress(0, "videos.zip");
      const zipBlob = await zip.generateAsync({ type: "blob" }, (meta) =>
        jobs.setZipProgress(meta.percent, "videos.zip")
      );
      downloadBlob(zipBlob, "videos.zip");
    } catch (e) {
      $("err").textContent = friendlyError(e);
    } finally {
      zipping = false;
      $("zip").disabled = outputs.length === 0;
    }
  });

  $("savedir").addEventListener("click", async () => {
    if (zipping || saving || !outputs.length) return;
    saving = true;
    $("savedir").disabled = true;
    try {
      const dir = await pickOutputDirectory();
      const written = await saveBlobsToDirectory(dir, outputs);
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

  async function listFiles(ff, re) {
    try {
      const names = await ff.listDir("/");
      return (names || []).map((x) => (typeof x === "string" ? x : x.name)).filter((n) => re.test(n));
    } catch {
      return [];
    }
  }

  async function ensureJszipV() {
    if (globalThis.JSZip) return;
    try {
      await loadScriptFirstOnce(JSZIP_URLS);
    } catch {
      throw new AppError("视频处理失败", `无法加载依赖: ${JSZIP_URLS.join(" / ")}`);
    }
    if (!globalThis.JSZip) throw new AppError("视频处理失败", "JSZip 加载失败");
  }
}
