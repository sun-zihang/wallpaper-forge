import { enableDragSave } from "./download.js";

export const STATUS_TEXT = {
  pending: "等待",
  running: "处理中",
  done: "完成",
  failed: "失败",
  cancelled: "已取消",
};

export function createJobList(container, { onCancel, onReport } = {}) {
  container.innerHTML = `
    <div class="row">
      <button type="button" class="btn secondary" data-act="cancel" disabled>取消</button>
      <span class="batch" aria-live="polite"></span>
      <span class="pct">0%</span>
    </div>
    <div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-label="转换进度"><i style="width:0%"></i></div>
    <div class="zip-progress" hidden>
      <div class="row">
        <span class="zip-name">打包</span>
        <span class="zip-pct" aria-live="polite">0%</span>
      </div>
      <div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-label="打包进度"><i style="width:0%"></i></div>
    </div>
    <div class="panel sheet">
      <table class="jobs">
        <thead><tr><th>预览</th><th>文件</th><th>状态</th></tr></thead>
        <tbody></tbody>
      </table>
      <div class="jobs-empty">还没有添加文件</div>
    </div>
  `;
  const tbody = container.querySelector("tbody");
  const emptyEl = container.querySelector(".jobs-empty");
  const bar = container.querySelector(".progress > i");
  const progressEl = container.querySelector(".progress");
  const pctLabel = container.querySelector(".pct");
  const cancelBtn = container.querySelector('[data-act="cancel"]');
  const batchEl = container.querySelector(".batch");
  const zipRow = container.querySelector(".zip-progress");
  const zipProgressEl = container.querySelector(".zip-progress .progress");
  const zipBar = container.querySelector(".zip-progress .progress > i");
  const zipPct = container.querySelector(".zip-pct");
  const zipName = container.querySelector(".zip-name");
  let cancelled = false;
  const rows = new Map();
  const thumbs = new Set();

  function releaseThumbs() {
    for (const url of thumbs) URL.revokeObjectURL(url);
    thumbs.clear();
  }

  cancelBtn.addEventListener("click", () => {
    if (cancelBtn.disabled) return;
    cancelBtn.disabled = true;
    cancelled = true;
    if (onCancel) onCancel();
  });

  function renderStatus(id, status, detail = "") {
    const tr = rows.get(id);
    if (!tr) return;
    const td = tr.querySelector("td.status");
    td.className = `status st-${status}`;
    td.textContent = STATUS_TEXT[status] || status;
    if (detail && (status === "failed" || status === "cancelled")) {
      td.textContent = `${STATUS_TEXT[status]}（${detail}）`;
      td.title = detail;
    }
    if (onReport) onReport({ id, status, detail });
  }

  function syncEmpty() {
    if (emptyEl) emptyEl.hidden = rows.size > 0;
  }

  syncEmpty();

  return {
    get cancelled() {
      return cancelled;
    },
    reset() {
      cancelled = false;
      releaseThumbs();
      tbody.innerHTML = "";
      rows.clear();
      bar.style.width = "0%";
      if (pctLabel) pctLabel.textContent = "0%";
      if (batchEl) batchEl.textContent = "";
      if (zipRow) zipRow.hidden = true;
      if (zipBar) zipBar.style.width = "0%";
      if (zipPct) zipPct.textContent = "0%";
      cancelBtn.disabled = true;
      syncEmpty();
    },
    submit(jobs) {
      this.reset();
      cancelBtn.disabled = !jobs.length;
      for (const job of jobs) {
        const tr = document.createElement("tr");
        tr.innerHTML =
          '<td class="thumb"></td><td class="name"></td><td class="status st-pending"></td>';
        tr.cells[1].textContent = job.name;
        if (job.thumb) {
          const img = document.createElement("img");
          img.src = job.thumb;
          img.alt = "";
          thumbs.add(job.thumb);
          tr.cells[0].appendChild(img);
        }
        tbody.appendChild(tr);
        rows.set(job.id, tr);
        renderStatus(job.id, "pending");
      }
      syncEmpty();
    },
    setProgress(pct) {
      const v = Math.max(0, Math.min(100, pct | 0));
      bar.style.width = `${v}%`;
      if (progressEl && progressEl.setAttribute) progressEl.setAttribute("aria-valuenow", String(v));
      if (pctLabel) pctLabel.textContent = `${v}%`;
    },
    setBatch(current, total, name) {
      if (!batchEl) return;
      const t = total | 0;
      if (!t || !name) {
        batchEl.textContent = "";
        return;
      }
      const idx = Math.min(Math.max(0, current | 0) + 1, t);
      const short = name.length > 24 ? `${name.slice(0, 14)}…${name.slice(-7)}` : name;
      batchEl.textContent = `${idx}/${t} · ${short}`;
      batchEl.title = name;
    },
    setZipProgress(pct, label) {
      if (!zipRow) return;
      zipRow.hidden = false;
      const v = Math.max(0, Math.min(100, pct | 0));
      if (zipName && label) zipName.textContent = `打包 ${label}`;
      if (zipBar) zipBar.style.width = `${v}%`;
      if (zipPct) zipPct.textContent = `${v}%`;
      if (zipProgressEl && zipProgressEl.setAttribute) zipProgressEl.setAttribute("aria-valuenow", String(v));
    },
    setStatus(id, status, detail) {
      renderStatus(id, status, detail);
    },
    setOutputBlob(id, { blob, filename }) {
      const tr = rows.get(id);
      if (!tr || !tr.cells || !tr.cells[0]) return;
      enableDragSave(tr.cells[0], blob, filename);
    },
    finish() {
      cancelBtn.disabled = true;
    },
  };
}
