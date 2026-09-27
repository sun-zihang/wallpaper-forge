// web/pages/home.js
import { bindDocumentDrop } from "../lib/drop.js";

function detectModule(file) {
  const name = (file && file.name || "").toLowerCase();
  if (name.endsWith(".gif")) return "gif";
  if ([".mp4", ".webm", ".mov", ".mkv"].some((e) => name.endsWith(e))) return "video";
  if ([".pkg", ".tex", ".mpkg"].some((e) => name.endsWith(e))) return "unpack";
  if ([".png", ".jpg", ".jpeg", ".webp", ".bmp"].some((e) => name.endsWith(e))) return "image";
  return null;
}

export function mountHome(root) {
  root.innerHTML = `
    <div class="home-hero">
      <h1>在浏览器里处理壁纸</h1>
      <p>图片、GIF、视频与 Wallpaper Engine 专有格式的转换与解包，全部在本机完成：文件不会离开你的浏览器。</p>
      <div class="home-drop" id="homeDrop" role="button" tabindex="0" aria-label="拖拽文件到这里">
        <span class="home-drop-main">拖拽文件到这里，自动识别并进入对应工具</span>
        <span class="home-drop-formats">JPG · PNG · WebP · MP4 · WebM · GIF · PKG · TEX · MPKG</span>
      </div>
    </div>
    <div class="cards">
      <a class="card" href="#/image"><b>图片转换</b><small>格式互转 / 缩放 / 裁剪 / 水印</small></a>
      <a class="card" href="#/gif"><b>GIF 工具</b><small>拆帧为 PNG 序列 / 图片合成 GIF</small></a>
      <a class="card" href="#/video"><b>视频转换</b><small>互转 / 转 GIF / 截取 / 帧率码率</small></a>
      <a class="card" href="#/unpack"><b>项目解包</b><small>.pkg / .tex / .mpkg，产物打包下载</small></a>
      <a class="card" href="#/settings"><b>设置</b><small>主题 / 默认参数 / 缓存管理</small></a>
      <a class="card" href="https://github.com/sun-zihang/wallpaper-forge/releases" target="_blank" rel="noopener"><b>桌面版</b><small>无大小限制 / GPU 加速 / 去水印</small></a>
    </div>
    <div class="home-trust">
      <div class="trust"><b>100% 本地</b><small>文件不离开浏览器</small></div>
      <div class="trust"><b>0 上传</b><small>无需注册登录</small></div>
      <div class="trust"><b>开源引擎</b><small>FFmpeg / gifuct / jszip</small></div>
    </div>
    <div class="note">
      去水印（图片修复 / 视频 delogo）仅桌面版，请使用上方「桌面版」卡片下载。
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
  bindDocumentDrop();
}
