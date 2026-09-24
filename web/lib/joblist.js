export const STATUS_TEXT = {
  pending: "等待",
  running: "处理中",
  done: "完成",
  failed: "失败",
  cancelled: "已取消",
};

export function createJobList(container, { onCancel } = {}) {
  container.innerHTML = `
    <div class="row">
      <button type="button" class="btn secondary" data-act="cancel" disabled>取消</button>
      <span class="pct">0%</span>
    </div>
    <div class="progress"><i style="width:0%"></i></div>
    <div class="panel sheet">
      <table class="jobs">
        <thead><tr><th>预览</th><th>文件</th><th>状态</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
  `;
  const tbody = container.querySelector("tbody");
  const bar = container.querySelector(".progress > i");
  const pctLabel = container.querySelector(".pct");
  const cancelBtn = container.querySelector('[data-act="cancel"]');
  let cancelled = false;
  const rows = new Map();
  const thumbs = new Set();

  function releaseThumbs() {
    for (const url of thumbs) URL.revokeObjectURL(url);
    thumbs.clear();
  }

  cancelBtn.addEventListener("click", () => {
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
      td.textContent = status === "failed" ? `${STATUS_TEXT.failed}（${detail}）` : detail;
      td.title = detail;
    }
  }

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
      cancelBtn.disabled = true;
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
    },
    setProgress(pct) {
      const v = Math.max(0, Math.min(100, pct | 0));
      bar.style.width = `${v}%`;
      if (pctLabel) pctLabel.textContent = `${v}%`;
    },
    setStatus(id, status, detail) {
      renderStatus(id, status, detail);
    },
    finish() {
      cancelBtn.disabled = true;
    },
  };
}
