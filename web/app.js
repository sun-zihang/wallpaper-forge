// web/app.js
import { mountHome } from "./pages/home.js";
import { WEB_VERSION } from "./version.js";
import { DEP_VERSIONS } from "./lib/deps.js";
import { bindDocumentDrop } from "./lib/drop.js";

const routes = {
  "": mountHome,
  "/": mountHome,
};

const lazy = {
  "/image": () => import("./pages/image.js").then((m) => m.mountImage),
  "/gif": () => import("./pages/gif.js").then((m) => m.mountGif),
  "/video": () => import("./pages/video.js").then((m) => m.mountVideo),
  "/unpack": () => import("./pages/unpack.js").then((m) => m.mountUnpack),
};

export function setStatus(text) {
  const el = document.getElementById("status");
  if (el) el.textContent = text;
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
  try {
    if (routes[hash]) {
      routes[hash](root);
      return;
    }
    if (lazy[hash]) {
      let mount;
      try {
        mount = await lazy[hash]();
      } catch {
        if (my === renderToken) location.hash = "#/";
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
window.addEventListener("hashchange", render);
render();
