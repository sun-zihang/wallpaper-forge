// web/pages/video.js
import { assertVideoLimits, probeVideoDuration, durationTooLongError, MAX_VIDEO_BYTES, MAX_VIDEO_SECONDS } from "../lib/video_limits.js";
import { ensureFFmpeg, readFileToBlob, runFFmpeg, writeFileFromBlob } from "../lib/video_bridge.js";
import { validateVideoFile } from "../lib/validate.js";
import { createJobList } from "../lib/joblist.js";
import { batchPct } from "../lib/progress.js";
import { attachDropTarget } from "../lib/drop.js";
import { JSZIP_URLS, loadScriptFirstOnce } from "../lib/cdn.js";
import { downloadBlob, stem, supportsFileSystemAccess, pickOutputDirectory, saveBlobsToDirectory } from "../lib/download.js";
import { friendlyError, AppError } from "../lib/errors.js";
import { detectMobile, mobileScaleArgs, MOBILE_MAX_VIDEO_WIDTH, MOBILE_VIDEO_NOTE } from "../lib/mobile.js";
import { setStatus } from "../app.js";
import { registerShortcutAction } from "../lib/shortcuts.js";
import { showToast } from "../lib/toast.js";
import { loadSettings } from "../lib/settings.js";

export function mountVideo(root) {
  root.innerHTML = `
    <div class="page-head">
      <h1>视频</h1>
      <p>格式互转、转 GIF、截帧与片段截取。引擎按需加载（数十 MB，首次较慢）。</p>
    </div>
    <div class="drop-bay" id="dropzone">
      <div class="row">
        <div class="field">
          <label for="files">选择视频</label>
          <input type="file" id="files" accept="video/*,.mp4,.webm,.mov,.mkv" multiple />
        </div>
        <span class="drop-hint">单文件 ≤ ${Math.round(MAX_VIDEO_BYTES / 1024 / 1024)}MB 且 ≤ ${MAX_VIDEO_SECONDS}s，超出请用桌面版</span>
      </div>
    </div>
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
          <label for="fps">帧率</label>
          <input type="number" id="fps" min="1" max="50" value="15" />
        </div>
        <div class="field" id="gifw2" hidden>
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
      <div class="row">
        <button type="button" class="btn" id="start">开始转换</button>
        <button type="button" class="btn secondary" id="zip" disabled>打包下载 ZIP</button>
        <button type="button" class="btn secondary" id="savedir" hidden>保存到文件夹</button>
      </div>
      <p class="mobile-note" id="mobile_note" hidden></p>
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
  let running = false;
  let zipping = false;
  let saving = false;
  const outputs = [];

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
  if ([...$("fmt").options].some((o) => o.value === settings.videoFormat)) {
    $("fmt").value = settings.videoFormat;
  }
  $("crf").value = String(settings.videoCrf);
  $("crf_v").textContent = String(settings.videoCrf);

  attachDropTarget($("dropzone"), $("files"), {
    extensions: [".mp4", ".webm", ".mov", ".mkv"],
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

  function syncMode() {
    const m = $("mode").value;
    $("fmtw").hidden = m !== "convert";
    $("converw").hidden = m !== "convert";
    $("gifw").hidden = m !== "gif";
    $("gifw2").hidden = m !== "gif";
    $("everyw").hidden = m !== "frames";
    $("trimw").hidden = m !== "trim";
    $("start").textContent =
      m === "convert" ? "开始转换" : m === "gif" ? "转 GIF" : m === "frames" ? "截取帧" : "片段截取";
  }
  $("mode").addEventListener("change", syncMode);
  syncMode();

  $("crf").addEventListener("input", () => ($("crf_v").textContent = $("crf").value));
  $("tfps").addEventListener("input", () => {
    const v = Number($("tfps").value) || 0;
    $("tfps_v").textContent = v > 0 ? `${v}fps` : "不转换";
  });

  // Mobile WASM throughput is far below desktop; cap transcode parameters to
  // 1080P-class and say so once instead of letting a 4K job crawl or OOM.
  const mobile = detectMobile();
  if (mobile) {
    $("mobile_note").textContent = MOBILE_VIDEO_NOTE;
    $("mobile_note").hidden = false;
    $("gw").max = String(MOBILE_MAX_VIDEO_WIDTH);
    if (Number($("gw").value) > MOBILE_MAX_VIDEO_WIDTH) $("gw").value = String(MOBILE_MAX_VIDEO_WIDTH);
  }

  $("start").addEventListener("click", async () => {
    if (running) return;
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
    running = true;
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
        await ensureFFmpeg((msg) => setStatus(msg));
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
          const out = await processOne(files[i], mode, (p) =>
            jobs.setProgress(batchPct(i, p, files.length))
          );
          if (out) {
            outputs.push(out);
            jobs.setStatus(i, "done");
            syncSaveDir();
          } else {
            jobs.setStatus(i, "failed", "没有产出文件");
          }
        } catch (e) {
          const msg = friendlyError(e);
          const cancelled = msg.includes("已取消");
          jobs.setStatus(i, cancelled ? "cancelled" : "failed", msg);
          if (cancelled) continue;
        }
      }
      jobs.finish();
      if (outputs.length) showToast(`转换完成，共 ${outputs.length} 个文件`, "success");
      $("zip").disabled = outputs.length === 0;
      $("zip").textContent = outputs.length > 1 ? `打包下载 ZIP（${outputs.length}）` : "打包下载 ZIP";
      if (outputs.length === 1) {
        downloadBlob(outputs[0].blob, outputs[0].filename);
      }
    } finally {
      running = false;
      $("start").disabled = false;
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
      downloadBlob(await zip.generateAsync({ type: "blob" }), "videos.zip");
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

  async function processOne(file, mode, onPct) {
    await validateVideoFile(file);
    const ff = await ensureFFmpeg();
    const inName = `in_${file.name.replace(/[^\w.-]+/g, "_")}`;
    await writeFileFromBlob(ff, inName, file);
    // every virtual file this job touches; the finally block guarantees the
    // MEMFS is drained on success, failure, and cancel alike
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
          `fps=${$("fps").value},scale=${$("gw").value}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer`,
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
          ...(mobile ? mobileScaleArgs(MOBILE_MAX_VIDEO_WIDTH) : []),
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
}

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
