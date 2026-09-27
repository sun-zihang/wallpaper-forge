// web/app.js
import { mountHome } from "./pages/home.js";
import { WEB_VERSION } from "./version.js";
import { DEP_VERSIONS } from "./lib/deps.js";
import { bindDocumentDrop } from "./lib/drop.js";
import { createMemoryMonitor } from "./lib/memory.js";
import { onVisibilityChange } from "./lib/visibility.js";
import { clearShortcutActions, installGlobalShortcuts } from "./lib/shortcuts.js";
import { maybeShowOnboarding } from "./lib/onboarding.js";
import { showErrorModal, installCompatBanner } from "./lib/errors-ui.js";

const routes = {
  "": mountHome,
  "/": mountHome,
};

const lazy = {
  "/image": () => import("./pages/image.js").then((m) => m.mountImage),
  "/gif": () => import("./pages/gif.js").then((m) => m.mountGif),
  "/video": () => import("./pages/video.js").then((m) => m.mountVideo),
  "/unpack": () => import("./pages/unpack.js").then((m) => m.mountUnpack),
  "/settings": () => import("./pages/settings.js").then((m) => m.mountSettings),
  "/desktop": () => import("./pages/desktop.js").then((m) => m.mountDesktop),
  "/jobs": () => import("./pages/jobs.js").then((m) => m.mountJobs),
};

export function setStatus(text) {
  const el = document.getElementById("status");
  if (el) el.textContent = text;
}

export function setTaskRunning(running) {
  window.__wcRunning = !!running;
}

export function getRenderToken() {
  return renderToken;
}

function markActive(hash) {
  for (const a of document.querySelectorAll(".rail nav a")) {
    const href = a.getAttribute("href").replace(/^#/, "") || "/";
    a.classList.toggle("active", href === hash);
  }
}

function renderFooter() {
  const el = document.getElementById("footer");
  if (!el) return;
  const deps = Object.entries(DEP_VERSIONS)
    .map(([k, v]) => `<span class="mono">${k} ${v}</span>`)
    .join("");
  el.innerHTML = `
    <span class="mono">v${WEB_VERSION}</span>
    <span>文件只在本机浏览器处理，不会上传。</span>
    ${deps}
    <a href="https://github.com/sun-zihang/wallpaper-forge/releases" target="_blank" rel="noopener">桌面版下载</a>
  `;
}

let renderToken = 0;

async function render() {
  const my = ++renderToken;
  const hash = location.hash.replace(/^#/, "") || "/";
  const root = document.getElementById("app");
  markActive(hash);
  root.innerHTML = "";
  clearShortcutActions();
  try {
    if (routes[hash]) {
      routes[hash](root);
      return;
    }
    if (lazy[hash]) {
      let mount;
      try {
        mount = await lazy[hash]();
      } catch (e) {
        // a module that fails to load is worth seeing (syntax errors, CDN
        // outage); log it, tell the user, and fall back to the home page
        console.error("页面加载失败", e);
        if (my === renderToken) {
          setStatus("页面加载失败，请刷新重试");
          location.hash = "#/";
        }
        return;
      }
      if (my !== renderToken) return;
      mount(root);
      return;
    }
    location.hash = "#/";
  } catch (e) {
    root.innerHTML = `<pre class="err"></pre>`;
    root.querySelector("pre").textContent = String(e);
  }
}

renderFooter();
bindDocumentDrop();
installGlobalShortcuts();
installCompatBanner();

window.addEventListener("beforeunload", (e) => {
  if (window.__wcRunning) {
    e.preventDefault();
    e.returnValue = "";
  }
});

let memoryWarned = false;
createMemoryMonitor({
  onWarning: (mb) => {
    if (memoryWarned) return;
    memoryWarned = true;
    showErrorModal({
      title: "内存使用过高",
      body: `当前处理任务已占用约 ${Math.round(mb)}MB 内存，接近浏览器安全上限。<br><br>建议：减少同时处理的文件数量、降低输出分辨率、或使用桌面版（无内存限制）。`,
      actions: [
        { label: "继续使用", primary: true },
        { label: "下载桌面版", onClick: () => (location.hash = "#/desktop") },
      ],
    });
  },
});

const BACKGROUND_TEXT = "标签页在后台，任务继续运行";
onVisibilityChange((hidden) => {
  const el = document.getElementById("status");
  if (hidden) {
    if (!el || el.textContent === "就绪") setStatus(BACKGROUND_TEXT);
  } else if (el && el.textContent === BACKGROUND_TEXT) {
    setStatus("就绪");
  }
});

maybeShowOnboarding();

window.addEventListener("hashchange", render);
render();
