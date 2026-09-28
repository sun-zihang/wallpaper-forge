// web/pages/home.js
import { bindDocumentDrop } from "../lib/drop.js";
import { getLang, setLang } from "../lib/i18n.js";

const STRINGS = {
  zh: {
    langButton: "English",
    aria: "拖拽文件到这里",
    heroTitle: "在浏览器里处理壁纸",
    heroSub: "图片、GIF、视频与 Wallpaper Engine 专有格式的转换与解包，全部在本机完成：文件不会离开你的浏览器。",
    dropMain: "拖拽文件到这里，自动识别并进入对应工具",
    dropFormats: "JPG · PNG · WebP · MP4 · WebM · GIF · PKG · TEX · MPKG",
    cards: [
      { href: "#/image", title: "图片转换", sub: "格式互转 / 缩放 / 裁剪 / 水印" },
      { href: "#/gif", title: "GIF 工具", sub: "拆帧为 PNG 序列 / 图片合成 GIF" },
      { href: "#/video", title: "视频转换", sub: "互转 / 转 GIF / 截取 / 帧率码率" },
      { href: "#/unpack", title: "项目解包", sub: ".pkg / .tex / .mpkg，产物打包下载" },
      { href: "#/settings", title: "设置", sub: "主题 / 默认参数 / 缓存管理" },
      { href: "#/desktop", title: "桌面版", sub: "无大小限制 / GPU 加速 / 去水印" },
    ],
    trust: [
      ["100% 本地", "文件不离开浏览器"],
      ["0 上传", "无需注册登录"],
      ["开源引擎", "FFmpeg / gifuct / jszip"],
    ],
    note: '去水印（图片修复 / 视频 delogo）暂仅桌面版提供。<a href="#/desktop">查看桌面版下载</a>',
    help: "我遇到了问题？提交 GitHub Issue 反馈",
  },
  en: {
    langButton: "中文",
    aria: "Drop files here",
    heroTitle: "Process wallpapers in your browser",
    heroSub: "Convert and unpack images, GIFs, videos and Wallpaper Engine's proprietary formats — all on your machine: files never leave your browser.",
    dropMain: "Drop files here — we detect the type and open the right tool",
    dropFormats: "JPG · PNG · WebP · MP4 · WebM · GIF · PKG · TEX · MPKG",
    cards: [
      { href: "#/image", title: "Image converter", sub: "Convert / resize / crop / watermark" },
      { href: "#/gif", title: "GIF tools", sub: "Extract frames to PNG / merge images into GIF" },
      { href: "#/video", title: "Video converter", sub: "Convert / to GIF / clip / fps & bitrate" },
      { href: "#/unpack", title: "Project unpacker", sub: ".pkg / .tex / .mpkg, results as ZIP" },
      { href: "#/settings", title: "Settings", sub: "Theme / defaults / cache" },
      { href: "#/desktop", title: "Desktop", sub: "No size limits / GPU accel / watermark removal" },
    ],
    trust: [
      ["100% local", "Files stay in your browser"],
      ["0 uploads", "No account needed"],
      ["Open-source engine", "FFmpeg / gifuct / jszip"],
    ],
    note: 'Watermark removal (image inpainting / video delogo) is desktop-only for now. <a href="#/desktop">Get the desktop version</a>',
    help: "Ran into a problem? Open a GitHub Issue",
  },
};

function detectModule(file) {
  const name = (file && file.name || "").toLowerCase();
  if (name.endsWith(".gif")) return "gif";
  if ([".mp4", ".webm", ".mov", ".mkv"].some((e) => name.endsWith(e))) return "video";
  if ([".pkg", ".tex", ".mpkg"].some((e) => name.endsWith(e))) return "unpack";
  if ([".png", ".jpg", ".jpeg", ".webp", ".bmp"].some((e) => name.endsWith(e))) return "image";
  return null;
}

export function mountHome(root) {
  let lang = getLang();

  const paint = () => {
    const t = STRINGS[lang];
    root.innerHTML = `
    <div class="home-hero">
      <h1>${t.heroTitle}</h1>
      <p>${t.heroSub}</p>
      <div class="home-drop" id="homeDrop" role="button" tabindex="0" aria-label="${t.aria}">
        <span class="home-drop-main">${t.dropMain}</span>
        <span class="home-drop-formats">${t.dropFormats}</span>
      </div>
    </div>
    <div class="cards">
      ${t.cards.map((c) => `<a class="card" href="${c.href}"><b>${c.title}</b><small>${c.sub}</small></a>`).join("")}
    </div>
    <div class="home-trust">
      ${t.trust.map(([b, s]) => `<div class="trust"><b>${b}</b><small>${s}</small></div>`).join("")}
    </div>
    <div class="note">${t.note}</div>
    <div class="home-help">
      <button type="button" id="langToggle" class="btn secondary">${t.langButton}</button>
      <a href="https://github.com/sun-zihang/wallpaper-forge/issues/new" target="_blank" rel="noopener noreferrer">${t.help}</a>
    </div>
  `;

    const drop = root.querySelector("#homeDrop");
    const route = (files) => {
      if (!files || !files.length) return;
      const mod = detectModule(files[0]);
      if (!mod) return;
      window.__wcHandoff = files;
      location.hash = `#/${mod}`;
    };
    drop.addEventListener("dragover", (ev) => {
      ev.preventDefault();
      drop.classList.add("hot");
    });
    drop.addEventListener("dragleave", () => drop.classList.remove("hot"));
    drop.addEventListener("drop", (ev) => {
      ev.preventDefault();
      drop.classList.remove("hot");
      route([...(ev.dataTransfer?.files || [])]);
    });
    drop.addEventListener("keydown", (ev) => {
      if (ev.key !== "Enter" && ev.key !== " ") return;
      ev.preventDefault();
      const input = document.createElement("input");
      input.type = "file";
      input.onchange = () => route([...(input.files || [])]);
      input.click();
    });
    root.querySelector("#langToggle").addEventListener("click", () => {
      lang = setLang(lang === "zh" ? "en" : "zh");
      paint();
    });
  };

  paint();
  bindDocumentDrop();
}
