// web/app.js
import { mountHome } from "./pages/home.js";

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

let renderToken = 0;

async function render() {
  const my = ++renderToken;
  const hash = location.hash.replace(/^#/, "") || "/";
  const root = document.getElementById("app");
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

window.addEventListener("hashchange", render);
render();
