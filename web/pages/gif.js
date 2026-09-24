// web/pages/gif.js
import { mergeGif, splitGif } from "../lib/gif_ops.js";
import { createJobList } from "../lib/joblist.js";
import { batchPct } from "../lib/progress.js";
import { validateSelection } from "../lib/selection.js";
import { attachDropTarget } from "../lib/drop.js";
import { JSZIP_URLS, loadScriptFirst } from "../lib/cdn.js";
import { downloadBlob } from "../lib/download.js";
import { friendlyError, AppError } from "../lib/errors.js";

const IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"];

export function mountGif(root) {
  root.innerHTML = `
    <div class="page-head">
      <h1>GIF 工具</h1>
      <p>拆帧按 delta 与 disposal 正确合成，与桌面版输出一致；合帧逐帧编码，可随时取消。</p>
    </div>
    <div class="drop-bay" id="dropzone">
      <div class="row">
        <div class="field">
          <label for="files">选择文件</label>
          <input type="file" id="files" multiple accept="image/*,.gif" />
        </div>
        <span class="drop-hint">或拖拽到此处</span>
      </div>
    </div>
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
        <div class="field" id="wdur" hidden>
          <label for="dur">帧间隔 (ms)</label>
          <input type="number" id="dur" min="10" max="5000" value="100" />
        </div>
        <div class="field" id="wrev" hidden>
          <label class="inline"><input type="checkbox" id="rev" /> 倒放</label>
        </div>
        <div class="field" id="wloop" hidden>
          <label class="inline"><input type="checkbox" id="loop" checked /> 无限循环</label>
        </div>
      </div>
      <div class="row">
        <button type="button" class="btn" id="start">开始</button>
        <button type="button" class="btn secondary" id="zip" hidden>打包下载 ZIP</button>
      </div>
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
  let splitFiles = [];
  let running = false;

  attachDropTarget($("dropzone"), $("files"), {
    extensions: IMAGE_EXTS,
    onRejected: (msg) => {
      $("err").textContent = msg;
    },
  });

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
    if (running) return;
    const err = $("err");
    err.textContent = "";
    token.cancelled = false;
    const files = [...$("files").files];
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
    running = true;
    $("start").disabled = true;
    $("zip").disabled = true;
    try {
      if ($("mode").value === "split") {
        jobs.submit(
          accepted.map((f, i) => ({ id: i, name: f.name, thumb: URL.createObjectURL(f) }))
        );
        splitFiles = [];
        for (let i = 0; i < accepted.length; i++) {
          if (jobs.cancelled) {
            jobs.setStatus(i, "cancelled", "已取消");
            continue;
          }
          jobs.setStatus(i, "running");
          jobs.setProgress(batchPct(i, 0, accepted.length));
          try {
            const { files: parts } = await splitGif(accepted[i], {
              step: Number($("step").value),
              token,
            });
            splitFiles.push(...parts);
            jobs.setStatus(i, "done");
            jobs.setProgress(batchPct(i, 100, accepted.length));
          } catch (e) {
            const msg = friendlyError(e);
            const cancelled = msg.includes("已取消");
            jobs.setStatus(i, cancelled ? "cancelled" : "failed", msg);
            if (cancelled) continue;
          }
        }
        jobs.finish();
        return;
      }
      // merge
      const ordered = [...accepted].sort((a, b) => a.name.localeCompare(b.name));
      jobs.submit([{ id: 0, name: ordered[0].name, thumb: URL.createObjectURL(ordered[0]) }]);
      jobs.setStatus(0, "running");
      try {
        const { blob, filename } = await mergeGif(ordered, {
          durationMs: Number($("dur").value),
          loop: $("loop").checked ? 0 : 1,
          reverse: $("rev").checked,
          token,
          onProgress: (done, totalFrames) =>
            jobs.setProgress(batchPct(0, (done / totalFrames) * 100, 1)),
        });
        jobs.setStatus(0, "done");
        downloadBlob(blob, filename);
      } catch (e) {
        const msg = friendlyError(e);
        const cancelled = msg.includes("已取消");
        jobs.setStatus(0, cancelled ? "cancelled" : "failed", msg);
      }
      jobs.finish();
    } finally {
      running = false;
      $("start").disabled = false;
      $("zip").disabled = false;
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
      downloadBlob(await zip.generateAsync({ type: "blob" }), "frames.zip");
    } catch (e) {
      $("err").textContent = friendlyError(e);
    }
  });
}

async function ensureJszipGif() {
  if (globalThis.JSZip) return;
  try {
    await loadScriptFirst(JSZIP_URLS);
  } catch {
    throw new AppError("GIF 处理失败", `无法加载依赖: ${JSZIP_URLS.join(" / ")}`);
  }
  if (!globalThis.JSZip) throw new AppError("GIF 处理失败", "JSZip 加载失败");
}
