// web/lib/toast.js
// 右上角滑入的轻量提示，3 秒后自动消失。
let container = null;

function ensureContainer() {
  if (container) return container;
  container = document.createElement("div");
  container.className = "toast-container";
  container.setAttribute("aria-live", "polite");
  document.body.appendChild(container);
  return container;
}

export function showToast(message, type = "info", { timeout = 3000 } = {}) {
  const c = ensureContainer();
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.setAttribute("role", type === "error" ? "alert" : "status");
  const icon = { success: "✅", error: "❌", warning: "⚠️", info: "ℹ️" }[type] || "";
  el.innerHTML = `<span class="toast-icon">${icon}</span><span class="toast-msg"></span><button type="button" class="toast-close" aria-label="关闭">×</button>`;
  el.querySelector(".toast-msg").textContent = message;
  el.querySelector(".toast-close").addEventListener("click", dismiss);
  c.appendChild(el);
  const timer = setTimeout(dismiss, timeout);
  function dismiss() {
    clearTimeout(timer);
    el.classList.add("out");
    setTimeout(() => el.remove(), 250);
  }
  return dismiss;
}
