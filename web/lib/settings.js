// web/lib/settings.js
// 全局偏好：localStorage 持久化 + 主题应用。页面只负责渲染表单。
const STORE_KEY = "wc.settings";

export const DEFAULT_SETTINGS = {
  theme: "dark",
  imageFormat: "JPG",
  imageQuality: 90,
  imageWidth: 1920,
  videoFormat: "mp4",
  videoCrf: 23,
  gifStep: 1,
  memoryLimitMb: 1500,
};

export function loadSettings() {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    return { ...DEFAULT_SETTINGS, ...(raw ? JSON.parse(raw) : {}) };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export function saveSettings(patch) {
  const next = { ...loadSettings(), ...patch };
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(next));
  } catch { /* storage unavailable */ }
  return next;
}

export function applyTheme(theme) {
  const sysLight =
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: light)").matches;
  const light = theme === "light" || (theme === "system" && sysLight);
  document.body.classList.toggle("light", light);
}
