// web/pages/image.js
import { OUT_FORMATS, IMAGE_EXTS, convertImage, loadImageBitmap } from "../lib/image_ops.js";
import { addImageWatermark, addTextWatermark, cropCanvas } from "../lib/annotate.js";
import { createJobList } from "../lib/joblist.js";
import { batchPct } from "../lib/progress.js";
import { validateSelection } from "../lib/selection.js";
import { attachDropTarget } from "../lib/drop.js";
import { JSZIP_URLS, loadScriptFirst } from "../lib/cdn.js";
import { downloadBlob, stem } from "../lib/download.js";
import { friendlyError, AppError } from "../lib/errors.js";

export function mountImage(root) {
  root.innerHTML = `
    <div class="page-head">
      <h1>图片转换</h1>
      <p>格式互转、等比缩放、裁剪与水印。批量结果先进入作业表，完成后可一次打包下载。</p>
    </div>
    <div class="drop-bay" id="dropzone">
      <div class="row">
        <div class="field">
          <label for="files">选择图片</label>
          <input type="file" id="files" multiple accept="image/*" />
        </div>
        <span class="drop-hint">或把图片拖到这里</span>
      </div>
    </div>
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
      <div class="row">
        <button type="button" class="btn" id="start">开始转换</button>
        <button type="button" class="btn secondary" id="zip">打包下载 ZIP</button>
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
    <div id="jobs"></div>
    <pre class="err" id="err"></pre>
  `;
  const jobs = createJobList(root.querySelector("#jobs"));
  const err = root.querySelector("#err");
  const $ = (id) => root.querySelector(`#${id}`);
  const outputs = [];
  let running = false;
  let zipping = false;

  attachDropTarget($("dropzone"), $("files"), {
    extensions: IMAGE_EXTS,
    onRejected: (msg) => {
      err.textContent = msg;
    },
  });

  $("q").addEventListener("input", () => ($("qv").textContent = $("q").value));
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
  $("markfile").addEventListener("change", () => {
    $("wmimg").classList.add("active");
    $("wmtext").classList.remove("active");
    $("wm_text_field").hidden = true;
    $("wm_scale_field").hidden = false;
  });
  $("scale").addEventListener("change", () => {
    $("sw").disabled = !$("scale").checked;
  });

  async function runOne(file, opts, jobName) {
    if (jobs.cancelled) throw new AppError("图片处理失败", "已取消");
    const { blob, filename } = await convertImage(file, opts);
    outputs.push({ blob, filename });
    return filename;
  }

  $("start").addEventListener("click", async () => {
    if (running || zipping) return;
    err.textContent = "";
    const picked = [...$("files").files];
    if (!picked.length) {
      err.textContent = "请先选择图片文件";
      return;
    }
    const check = validateSelection(picked, { extensions: IMAGE_EXTS });
    if (!check.ok) {
      err.textContent = check.errors.map((e) => `${e.name}：${e.reason}`).join("\n");
      return;
    }
    const files = check.files;
    const fmt = $("fmt").value;
    const quality = Number($("q").value);
    const maxWidth = $("scale").checked ? Number($("sw").value) : 0;
    running = true;
    $("start").disabled = true;
    $("zip").disabled = true;
    try {
      jobs.submit(
        files.map((f, i) => ({ id: i, name: f.name, thumb: URL.createObjectURL(f) }))
      );
      for (let i = 0; i < files.length; i++) {
        jobs.setStatus(i, "running");
        jobs.setProgress(batchPct(i, 0, files.length));
        try {
          await runOne(files[i], { format: fmt, quality, maxWidth });
          jobs.setStatus(i, "done");
          jobs.setProgress(batchPct(i, 100, files.length));
        } catch (e) {
          const msg = friendlyError(e);
          const cancelled = msg.includes("已取消");
          jobs.setStatus(i, cancelled ? "cancelled" : "failed", msg);
          if (cancelled) {
            for (let j = i + 1; j < files.length; j++) jobs.setStatus(j, "cancelled", "已取消");
            break;
          }
        }
      }
      jobs.finish();
    } finally {
      running = false;
      $("start").disabled = false;
      $("zip").disabled = false;
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
      const blob = await zip.generateAsync({ type: "blob" });
      downloadBlob(blob, "images.zip");
    } catch (e) {
      err.textContent = friendlyError(e);
    } finally {
      zipping = false;
      $("zip").disabled = false;
    }
  });

  async function firstBitmap() {
    const f = $("files").files[0];
    if (!f) throw new AppError("图片处理失败", "请先添加图片文件");
    return { file: f, bitmap: await loadImageBitmap(f) };
  }

  $("crop").addEventListener("click", async () => {
    err.textContent = "";
    try {
      const { file, bitmap } = await firstBitmap();
      const box = await pickBoxOnPage(bitmap);
      if (!box) return;
      const canvas = cropCanvas(bitmap, box);
      const blob = await new Promise((res, rej) =>
        canvas.toBlob((b) => (b ? res(b) : rej(new AppError("图片处理失败", "保存失败"))), "image/png")
      );
      const filename = `${stem(file.name)}_crop.png`;
      outputs.push({ blob, filename });
      downloadBlob(blob, filename);
      bitmap.close && bitmap.close();
    } catch (e) {
      err.textContent = friendlyError(e);
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
    const picked = [...$("files").files];
    if (!picked.length) {
      err.textContent = "请先选择图片文件";
      return;
    }
    const check = validateSelection(picked, { extensions: IMAGE_EXTS });
    if (!check.ok) {
      err.textContent = check.errors.map((e) => `${e.name}：${e.reason}`).join("\n");
      return;
    }
    const files = check.files;
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
    const mark = textMode ? null : $("markfile").files[0];
    if (!textMode && !mark) {
      err.textContent = "请先选择水印图片";
      return;
    }
    running = true;
    $("wm_apply").disabled = true;
    try {
      jobs.submit(
        files.map((f, i) => ({ id: i, name: f.name, thumb: URL.createObjectURL(f) }))
      );
      const produced = [];
      for (let i = 0; i < files.length; i++) {
        if (jobs.cancelled) {
          jobs.setStatus(i, "cancelled", "已取消");
          continue;
        }
        jobs.setStatus(i, "running");
        jobs.setProgress(batchPct(i, 0, files.length));
        try {
          const res = textMode
            ? await addTextWatermark(files[i], {
                text,
                fontSize,
                position,
                color: `rgba(255,255,255,${opacity})`,
              })
            : await addImageWatermark(files[i], mark, { scale, opacity, position });
          outputs.push({ blob: res.blob, filename: res.filename });
          produced.push({ blob: res.blob, filename: res.filename });
          jobs.setStatus(i, "done");
          jobs.setProgress(batchPct(i, 100, files.length));
        } catch (e) {
          const msg = friendlyError(e);
          jobs.setStatus(i, msg.includes("已取消") ? "cancelled" : "failed", msg);
        }
      }
      jobs.finish();
      if (produced.length === 1) {
        downloadBlob(produced[0].blob, produced[0].filename);
      }
    } finally {
      running = false;
      $("wm_apply").disabled = false;
    }
  });
}

async function ensureJszip() {
  if (globalThis.JSZip) return;
  try {
    await loadScriptFirst(JSZIP_URLS);
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
    const maxW = Math.min(window.innerWidth - 40, bitmap.width);
    const scale = Math.min(1, maxW / bitmap.width);
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
