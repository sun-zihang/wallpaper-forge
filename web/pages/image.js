// web/pages/image.js
import { OUT_FORMATS, convertImage } from "../lib/image_ops.js";
import { addImageWatermark, addTextWatermark, cropCanvas } from "../lib/annotate.js";
import { createJobList } from "../lib/joblist.js";
import { downloadBlob, stem } from "../lib/download.js";
import { friendlyError, AppError } from "../lib/errors.js";

export function mountImage(root) {
  root.innerHTML = `
    <div class="row">
      <label>文件 <input type="file" id="files" multiple accept="image/*" /></label>
      <label>格式
        <select id="fmt">${OUT_FORMATS.map((f) => `<option${f === "JPG" ? " selected" : ""}>${f}</option>`).join("")}</select>
      </label>
      <label>质量 <input type="range" id="q" min="1" max="100" value="90" /><span id="qv">90</span></label>
      <label><input type="checkbox" id="scale" /> 缩放到宽度</label>
      <input type="number" id="sw" value="1920" min="16" max="8192" disabled style="width:90px" />
      <button type="button" class="btn" id="start">开始转换</button>
      <button type="button" class="btn secondary" id="zip">打包下载 ZIP</button>
    </div>
    <div class="row">
      <button type="button" class="btn secondary" id="crop">裁剪第一张…</button>
      <button type="button" class="btn secondary" id="wmtext">文字水印…</button>
      <button type="button" class="btn secondary" id="wmimg">图片水印…</button>
      <input type="file" id="markfile" accept="image/*" hidden />
    </div>
    <div id="jobs"></div>
    <pre class="err" id="err"></pre>
  `;
  const jobs = createJobList(root.querySelector("#jobs"));
  const err = root.querySelector("#err");
  const $ = (id) => root.querySelector(`#${id}`);
  const outputs = [];

  $("q").addEventListener("input", () => ($("qv").textContent = $("q").value));
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
    err.textContent = "";
    const files = [...$("files").files];
    if (!files.length) {
      err.textContent = "请先选择图片文件";
      return;
    }
    const fmt = $("fmt").value;
    const quality = Number($("q").value);
    const maxWidth = $("scale").checked ? Number($("sw").value) : 0;
    jobs.submit(files.map((f, i) => ({ id: i, name: f.name })));
    for (let i = 0; i < files.length; i++) {
      jobs.setStatus(i, "running");
      try {
        await runOne(files[i], { format: fmt, quality, maxWidth });
        jobs.setStatus(i, "done");
      } catch (e) {
        const msg = friendlyError(e);
        const cancelled = msg.includes("已取消");
        jobs.setStatus(i, cancelled ? "cancelled" : "failed", msg);
        if (cancelled) break;
      }
    }
    jobs.finish();
  });

  $("zip").addEventListener("click", async () => {
    err.textContent = "";
    if (!outputs.length) {
      err.textContent = "还没有可下载的输出";
      return;
    }
    try {
      await ensureJszip();
      const zip = new globalThis.JSZip();
      for (const o of outputs) zip.file(o.filename, o.blob);
      const blob = await zip.generateAsync({ type: "blob" });
      downloadBlob(blob, "images.zip");
    } catch (e) {
      err.textContent = friendlyError(e);
    }
  });

  async function firstBitmap() {
    const f = $("files").files[0];
    if (!f) throw new AppError("图片处理失败", "请先添加图片文件");
    return { file: f, bitmap: await createImageBitmap(f) };
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

  $("wmtext").addEventListener("click", async () => {
    err.textContent = "";
    try {
      const { file, bitmap } = await firstBitmap();
      bitmap.close && bitmap.close();
      const text = prompt("水印文字", "我的壁纸");
      if (!text) return;
      const pos = prompt("位置 top_left|top_right|bottom_left|bottom_right|center", "bottom_right") || "bottom_right";
      const { blob, filename } = await addTextWatermark(file, { text, position: pos });
      outputs.push({ blob, filename });
      downloadBlob(blob, filename);
    } catch (e) {
      err.textContent = friendlyError(e);
    }
  });

  $("wmimg").addEventListener("click", async () => {
    err.textContent = "";
    try {
      const { file, bitmap } = await firstBitmap();
      bitmap.close && bitmap.close();
      $("markfile").click();
      $("markfile").onchange = async () => {
        err.textContent = "";
        try {
          const mark = $("markfile").files[0];
          if (!mark) return;
          const { blob, filename } = await addImageWatermark(file, mark, { scale: 0.2, opacity: 0.8, position: "bottom_right" });
          outputs.push({ blob, filename });
          downloadBlob(blob, filename);
        } catch (e) {
          err.textContent = friendlyError(e);
        }
      };
    } catch (e) {
      err.textContent = friendlyError(e);
    }
  });
}

async function ensureJszip() {
  if (globalThis.JSZip) return;
  await new Promise((res, rej) => {
    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js";
    s.onload = res;
    s.onerror = () => rej(new AppError("图片处理失败", "JSZip 加载失败"));
    document.head.appendChild(s);
  });
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
