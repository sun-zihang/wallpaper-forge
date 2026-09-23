// web/pages/home.js
export function mountHome(root) {
  root.innerHTML = `
    <div class="cards">
      <a class="card" href="#/image">图片转换<small>互转 / 缩放 / 裁剪 / 水印</small></a>
      <a class="card" href="#/gif">GIF 工具<small>拆帧 / 合帧</small></a>
      <a class="card" href="#/video">视频<small>互转 / 转 GIF / 截帧 / 片段（引擎按需加载）</small></a>
      <a class="card" href="#/unpack">解包<small>.pkg / .tex / .mpkg</small></a>
    </div>
    <div class="note">
      去水印（图片修复 / 视频 delogo）仅桌面版：
      <a href="https://github.com/sun-zihang/wallpaper-forge/releases" target="_blank" rel="noopener">下载桌面版</a>。
      所有文件仅在本机浏览器处理，不会上传。
    </div>
  `;
}
