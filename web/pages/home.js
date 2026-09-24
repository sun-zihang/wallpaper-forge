// web/pages/home.js
export function mountHome(root) {
  root.innerHTML = `
    <div class="page-head">
      <h1>在浏览器里处理壁纸</h1>
      <p>图片、GIF、视频与 Wallpaper Engine 专有格式的转换与解包，全部在本机完成：文件不会离开你的浏览器。</p>
    </div>
    <div class="cards">
      <a class="card" href="#/image"><b>图片转换</b><small>格式互转 / 缩放 / 裁剪 / 水印</small></a>
      <a class="card" href="#/gif"><b>GIF 工具</b><small>拆帧为 PNG 序列 / 图片合成 GIF</small></a>
      <a class="card" href="#/video"><b>视频</b><small>互转 / 转 GIF / 截帧 / 片段截取（引擎按需加载）</small></a>
      <a class="card" href="#/unpack"><b>解包</b><small>.pkg / .tex / .mpkg，产物打包下载</small></a>
    </div>
    <div class="note">
      去水印（图片修复 / 视频 delogo）仅桌面版：
      <a href="https://github.com/sun-zihang/wallpaper-forge/releases" target="_blank" rel="noopener">下载桌面版</a>。
    </div>
  `;
}
