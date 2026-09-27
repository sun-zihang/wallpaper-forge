// web/pages/jobs.js
import { getJobs, onJobChange, clearFinished, removeJob, moveJob } from "../lib/jobcenter.js";
import { downloadBlob } from "../lib/download.js";
import { JSZIP_URLS, loadScriptFirstOnce } from "../lib/cdn.js";
import { setStatus, getRenderToken } from "../app.js";

const STATUS_LABEL = {
  pending: "排队中",
  running: "处理中",
  done: "完成",
  failed: "失败",
  cancelled: "已取消",
};

export function mountJobs(root) {
  const pageToken = getRenderToken();
  root.innerHTML = `
    <div class="page-head">
      <h1>批量作业管理中心</h1>
      <p>跨页面作业队列。暂停、下载已完成、清除失败、调整顺序。</p>
    </div>
    <div class="panel">
      <div class="row">
        <button type="button" class="btn secondary" id="clearFinished">清除已完成和失败</button>
        <button type="button" class="btn" id="downloadAll">下载全部已完成 (ZIP)</button>
        <span class="drop-hint" id="jobStats"></span>
      </div>
    </div>
    <div class="panel">
      <table class="jobs">
        <thead>
          <tr><th>#</th><th>文件</th><th>来源</th><th>状态</th><th>进度</th><th>操作</th></tr>
        </thead>
        <tbody id="jobRows"></tbody>
      </table>
      <div class="jobs-empty" id="jobsEmpty" hidden>暂无作业</div>
    </div>
  `;
  const tbody = root.querySelector("#jobRows");
  const emptyEl = root.querySelector("#jobsEmpty");
  const statsEl = root.querySelector("#jobStats");

  function render() {
    if (pageToken !== getRenderToken()) return;
    const jobs = getJobs();
    tbody.innerHTML = "";
    emptyEl.hidden = jobs.length > 0;
    const done = jobs.filter((j) => j.status === "done").length;
    const running = jobs.filter((j) => j.status === "running").length;
    const pending = jobs.filter((j) => j.status === "pending").length;
    const failed = jobs.filter((j) => j.status === "failed").length;
    statsEl.textContent = `共 ${jobs.length} | 完成 ${done} | 处理中 ${running} | 排队 ${pending} | 失败 ${failed}`;
    jobs.forEach((job, i) => {
      const tr = document.createElement("tr");
      const statusText = STATUS_LABEL[job.status] || job.status;
      tr.innerHTML = `
        <td class="mono">${i + 1}</td>
        <td class="name"></td>
        <td>${job.page || "—"}</td>
        <td><span class="status st-${job.status}">${statusText}${job.detail ? `（${job.detail}）` : ""}</span></td>
        <td class="mono">${job.status === "running" ? `${job.progress}%` : "—"}</td>
        <td class="job-ops"></td>
      `;
      tr.cells[1].textContent = job.name;
      const ops = tr.cells[5];
      if (job.status === "done" && job.blob) {
        const dl = document.createElement("button");
        dl.className = "btn secondary";
        dl.textContent = "下载";
        dl.addEventListener("click", () => {
          const blob = job.blob instanceof Blob ? job.blob : new Blob([job.blob]);
          downloadBlob(blob, job.filename || job.name);
        });
        ops.appendChild(dl);
      }
      const up = document.createElement("button");
      up.className = "btn secondary";
      up.textContent = "↑";
      up.disabled = i === 0;
      up.addEventListener("click", () => moveJob(job.id, -1));
      ops.appendChild(up);
      const down = document.createElement("button");
      down.className = "btn secondary";
      down.textContent = "↓";
      down.disabled = i === jobs.length - 1;
      down.addEventListener("click", () => moveJob(job.id, 1));
      ops.appendChild(down);
      const rm = document.createElement("button");
      rm.className = "btn secondary";
      rm.textContent = "✕";
      rm.addEventListener("click", () => removeJob(job.id));
      ops.appendChild(rm);
      tbody.appendChild(tr);
    });
  }

  const off = onJobChange(render);
  render();

  root.querySelector("#clearFinished").addEventListener("click", () => {
    clearFinished();
    setStatus("已清除已完成和失败的作业");
  });

  root.querySelector("#downloadAll").addEventListener("click", async () => {
    const done = getJobs().filter((j) => j.status === "done" && j.blob);
    if (!done.length) {
      setStatus("没有已完成的作业");
      return;
    }
    try {
      if (!globalThis.JSZip) await loadScriptFirstOnce(JSZIP_URLS);
      const zip = new globalThis.JSZip();
      for (const j of done) {
        const blob = j.blob instanceof Blob ? j.blob : new Blob([j.blob]);
        zip.file(j.filename || j.name, blob);
      }
      downloadBlob(await zip.generateAsync({ type: "blob" }), "completed.zip");
    } catch (e) {
      setStatus(`打包失败：${e && e.message ? e.message : e}`);
    }
  });

  // cleanup on unmount
  window.addEventListener("hashchange", off, { once: true });
}
