// web/lib/errors-ui.js
// 通用错误弹窗与浏览器兼容性横幅。
export function showErrorModal({ title, body, actions = [{ label: "知道了" }] }) {
  const overlay = document.createElement("div");
  overlay.className = "error-modal";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-label", title);
  overlay.innerHTML = `
    <div class="error-modal-card">
      <h2></h2>
      <div class="error-modal-body"></div>
      <div class="error-modal-actions"></div>
    </div>
  `;
  overlay.querySelector("h2").textContent = title;
  overlay.querySelector(".error-modal-body").innerHTML = body;
  const actionsEl = overlay.querySelector(".error-modal-actions");
  for (const a of actions) {
    const btn = document.createElement("button");
    btn.className = `btn ${a.primary ? "" : "secondary"}`;
    btn.textContent = a.label;
    btn.addEventListener("click", () => {
      overlay.remove();
      if (a.onClick) a.onClick();
    });
    actionsEl.appendChild(btn);
  }
  document.body.appendChild(overlay);
  return overlay;
}

const REQUIRED_APIS = [
  ["createImageBitmap", "图片解码"],
  ["OffscreenCanvas", "离屏渲染"],
  ["showDirectoryPicker", "文件夹保存"],
];

export function missingRequiredApis() {
  const missing = [];
  if (typeof createImageBitmap !== "function") missing.push("createImageBitmap");
  if (typeof OffscreenCanvas === "undefined") missing.push("OffscreenCanvas");
  return missing;
}

export function installCompatBanner(onClose) {
  if (typeof document === "undefined" || !document.body) return;
  const missing = missingRequiredApis();
  // showDirectoryPicker is Chromium-only; its absence is not a hard error
  const hard = missing.filter((m) => m !== "showDirectoryPicker");
  if (!hard.length) return;
  const banner = document.createElement("div");
  banner.className = "compat-banner";
  banner.setAttribute("role", "alert");
  banner.innerHTML = `
    <span>⚠️ 你的浏览器缺少 ${hard.join("、")}，部分功能可能无法正常使用。建议使用最新版 Chrome / Edge 以获得最佳体验。</span>
    <button type="button" class="compat-close" aria-label="关闭">×</button>
  `;
  banner.querySelector(".compat-close").addEventListener("click", () => {
    banner.remove();
    if (onClose) onClose();
  });
  document.body.prepend(banner);
}
