// web/lib/shortcuts.js
// 全局键盘快捷键。页面通过 registerShortcutAction 注册动作，
// installGlobalShortcuts 安装一次全局监听；render 切换页面时清空注册表，
// 由新页面重新注册自己的动作。
const actions = {};

export function registerShortcutAction(name, fn) {
  actions[name] = fn;
}

export function clearShortcutActions() {
  for (const k of Object.keys(actions)) delete actions[k];
}

const SHORTCUTS = [
  ["Ctrl+O", "打开文件"],
  ["Ctrl+Enter", "开始处理"],
  ["Ctrl+S", "打包下载"],
  ["Esc", "取消 / 关闭"],
  ["?", "快捷键帮助"],
];

let helpEl = null;
let helpVisible = false;

function ensureHelpPanel() {
  if (helpEl) return helpEl;
  helpEl = document.createElement("div");
  helpEl.className = "shortcut-help";
  helpEl.setAttribute("role", "dialog");
  helpEl.setAttribute("aria-label", "键盘快捷键");
  helpEl.innerHTML = `
    <div class="shortcut-help-card">
      <div class="shortcut-help-head">
        <span>⌨️ 键盘快捷键</span>
        <button type="button" class="shortcut-help-close" aria-label="关闭">×</button>
      </div>
      <table class="shortcut-help-table">
        <tbody>
          ${SHORTCUTS.map(([k, d]) => `<tr><td class="mono">${k}</td><td>${d}</td></tr>`).join("")}
        </tbody>
      </table>
    </div>
  `;
  document.body.appendChild(helpEl);
  helpEl.querySelector(".shortcut-help-close").addEventListener("click", hideShortcutHelp);
  helpEl.addEventListener("click", (ev) => {
    if (ev.target === helpEl) hideShortcutHelp();
  });
  return helpEl;
}

export function toggleShortcutHelp() {
  const el = ensureHelpPanel();
  helpVisible = !helpVisible;
  el.classList.toggle("open", helpVisible);
}

export function hideShortcutHelp() {
  if (!helpEl) return;
  helpVisible = false;
  helpEl.classList.remove("open");
}

export function isShortcutHelpVisible() {
  return helpVisible;
}

export function installGlobalShortcuts() {
  window.addEventListener("keydown", (ev) => {
    const t = ev.target;
    const tag = (t && t.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    if (ev.key === "?" || (ev.shiftKey && ev.key === "/")) {
      ev.preventDefault();
      toggleShortcutHelp();
      return;
    }
    if (ev.key === "Escape") {
      if (helpVisible) {
        hideShortcutHelp();
        return;
      }
      if (actions.onCancel) {
        ev.preventDefault();
        actions.onCancel();
      }
      return;
    }
    const mod = ev.ctrlKey || ev.metaKey;
    if (!mod) return;
    const key = ev.key.toLowerCase();
    if (key === "o") {
      ev.preventDefault();
      if (actions.onOpen) actions.onOpen();
    } else if (ev.key === "Enter") {
      ev.preventDefault();
      if (actions.onStart) actions.onStart();
    } else if (key === "s") {
      ev.preventDefault();
      if (actions.onDownload) actions.onDownload();
    }
  });
}
