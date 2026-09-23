// web/pages/unpack.js
import { extractMpkg } from "../lib/we_mpkg.js";
import { extractPkg } from "../lib/we_pkg.js";
import { extractTex } from "../lib/we_tex.js";
import { detectKind } from "../lib/we_detect.js";
import { createJobList } from "../lib/joblist.js";
import { downloadBlob, stem } from "../lib/download.js";
import { friendlyError, AppError } from "../lib/errors.js";

export function mountUnpack(root) {
  root.innerHTML = `
    <div class="row">
      <label>文件 <input type="file" id="files" multiple accept=".pkg,.tex,.mpkg" /></label>
      <button type="button" class="btn" id="start">开始解包</button>
      <button type="button" class="btn secondary" id="dl">打包下载 ZIP</button>
    </div>
    <div id="jobs"></div>
    <pre class="err" id="err"></pre>
  `;
  const $ = (id) => root.querySelector(`#${id}`);
  const jobs = createJobList(root.querySelector("#jobs"), { onCancel() {} });
  let allFiles = [];

  $("start").addEventListener("click", async () => {
    $("err").textContent = "";
    const files = [...$("files").files];
    if (!files.length) {
      $("err").textContent = "请先添加 .pkg / .tex / .mpkg 文件";
      return;
    }
    jobs.submit(files.map((f, i) => ({ id: i, name: f.name })));
    allFiles = [];
    for (let i = 0; i < files.length; i++) {
      if (jobs.cancelled) {
        jobs.setStatus(i, "cancelled", "已取消");
        continue;
      }
      const f = files[i];
      const kind = detectKind(f.name);
      if (!kind) {
        jobs.setStatus(i, "failed", "不支持的文件类型");
        continue;
      }
      jobs.setStatus(i, "running");
      try {
        const buf = new Uint8Array(await f.arrayBuffer());
        const base = stem(f.name);
        let result;
        if (kind === "pkg") result = extractPkg(buf);
        else if (kind === "tex") result = { files: [extractTex(buf, base)] };
        else result = extractMpkg(buf);
        for (const item of result.files) allFiles.push(item);
        jobs.setStatus(i, "done");
      } catch (e) {
        jobs.setStatus(i, "failed", friendlyError(e));
      }
    }
    jobs.finish();
  });

  $("dl").addEventListener("click", async () => {
    try {
      if (!allFiles.length) {
        $("err").textContent = "还没有解包结果";
        return;
      }
      await new Promise((res, rej) => {
        if (globalThis.JSZip) return res();
        const s = document.createElement("script");
        s.src = "https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js";
        s.onload = res;
        s.onerror = () => rej(new AppError("解包失败", "JSZip 加载失败"));
        document.head.appendChild(s);
      });
      const zip = new globalThis.JSZip();
      for (const f of allFiles) zip.file(f.name, f.blob);
      downloadBlob(await zip.generateAsync({ type: "blob" }), "unpacked.zip");
    } catch (e) {
      $("err").textContent = friendlyError(e);
    }
  });
}
