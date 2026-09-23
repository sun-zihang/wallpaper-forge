// web/pages/video.js
import { assertVideoLimits, probeVideoDuration, durationTooLongError, MAX_VIDEO_BYTES, MAX_VIDEO_SECONDS } from "../lib/video_limits.js";
import { ensureFFmpeg, readFileToBlob, runFFmpeg, writeFileFromBlob } from "../lib/video_bridge.js";
import { createJobList } from "../lib/joblist.js";
import { downloadBlob, stem } from "../lib/download.js";
import { friendlyError, AppError } from "../lib/errors.js";
import { setStatus } from "../app.js";

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
  let running = false;

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
          await processOne(files[i], mode, (p) => jobs.setProgress(p));
          jobs.setStatus(i, "done");
        } catch (e) {
          const msg = friendlyError(e);
          const cancelled = msg.includes("已取消");
          jobs.setStatus(i, cancelled ? "cancelled" : "failed", msg);
          if (cancelled) continue;
        }
      }
      jobs.finish();
    } finally {
      running = false;
      $("start").disabled = false;
    }
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
      try {
        await ff.deleteFile(out);
      } catch { /* ignore */ }
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
      try {
        await ff.deleteFile(out);
      } catch { /* ignore */ }
    } else if (mode === "frames") {
      const pattern = `frame_%04d.png`;
      const args = ["-i", inName, "-vf", `fps=1/${$("every").value}`, pattern];
      await runFFmpeg({ args, outPath: pattern, onProgress: onPct, cancelToken: token });
      const names = await listFiles(ff, /frame_\d+\.png$/);
      await ensureJszipV();
      const zip = new globalThis.JSZip();
      for (const n of names) zip.file(n, await readFileToBlob(ff, n));
      downloadBlob(await zip.generateAsync({ type: "blob" }), `${base}_frames.zip`);
      for (const n of names) {
        try {
          await ff.deleteFile(n);
        } catch { /* ignore */ }
      }
    } else {
      const out = `${base}_trim.mp4`;
      const t0 = Math.max(0, Number($("t0").value) || 0);
      const t1 = Math.max(t0 + 0.1, Number($("t1").value) || t0 + 0.1);
      const args = [
        "-ss", String(t0), "-i", inName, "-t", String(t1 - t0),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", out,
      ];
      await runFFmpeg({ args, outPath: out, onProgress: onPct, cancelToken: token });
      downloadBlob(await readFileToBlob(ff, out), out);
      try {
        await ff.deleteFile(out);
      } catch { /* ignore */ }
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

async function ensureJszipV() {
  if (globalThis.JSZip) return;
  await new Promise((res, rej) => {
    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js";
    s.onload = res;
    s.onerror = () => rej(new AppError("视频处理失败", "JSZip 加载失败"));
    document.head.appendChild(s);
  });
}
