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
          const cancelled = msg.includes("已取消");
          jobs.setStatus(i, cancelled ? "cancelled" : "failed", msg);
          if (cancelled) continue;
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
      const cancelled = msg.includes("已取消");
      jobs.setStatus(0, cancelled ? "cancelled" : "failed", msg);
    }
    jobs.finish();
  });

  $("zip").addEventListener("click", async () => {
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
  await new Promise((res, rej) => {
    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js";
    s.onload = res;
    s.onerror = () => rej(new AppError("GIF 处理失败", "JSZip 加载失败"));
    document.head.appendChild(s);
  });
}
