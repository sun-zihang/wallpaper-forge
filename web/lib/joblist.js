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
    </div>
    <div class="progress"><i style="width:0%"></i></div>
    <table class="jobs">
      <thead><tr><th>文件</th><th>状态</th></tr></thead>
      <tbody></tbody>
    </table>
  `;
  const tbody = container.querySelector("tbody");
  const bar = container.querySelector(".progress > i");
  const cancelBtn = container.querySelector('[data-act="cancel"]');
  let cancelled = false;
  const rows = new Map();

  cancelBtn.addEventListener("click", () => {
    cancelled = true;
    if (onCancel) onCancel();
  });

  function renderStatus(id, status, detail = "") {
    const tr = rows.get(id);
    if (!tr) return;
    const td = tr.querySelector("td:last-child");
    td.className = `st-${status}`;
    td.textContent = STATUS_TEXT[status] || status;
    if (detail && (status === "failed" || status === "cancelled")) {
      td.textContent = status === "failed" ? `${STATUS_TEXT.failed}（${detail}）` : detail;
    }
  }

  return {
    get cancelled() {
      return cancelled;
    },
    reset() {
      cancelled = false;
      tbody.innerHTML = "";
      rows.clear();
      bar.style.width = "0%";
      cancelBtn.disabled = true;
    },
    submit(jobs) {
      this.reset();
      cancelBtn.disabled = false;
      for (const job of jobs) {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td></td><td class="st-pending"></td>`;
        tr.cells[0].textContent = job.name;
        tbody.appendChild(tr);
        rows.set(job.id, tr);
        renderStatus(job.id, "pending");
      }
    },
    setProgress(pct) {
      const v = Math.max(0, Math.min(100, pct | 0));
      bar.style.width = `${v}%`;
    },
    setStatus(id, status, detail) {
      renderStatus(id, status, detail);
    },
    finish() {
      cancelBtn.disabled = true;
    },
  };
}
