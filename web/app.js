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

async function render() {
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
        location.hash = "#/";
        return;
      }
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
