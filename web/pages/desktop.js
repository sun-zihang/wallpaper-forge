// web/pages/desktop.js
import { registerShortcutAction } from "../lib/shortcuts.js";
import { trackDesktop } from "../lib/track.js";

const RELEASES_URL = "https://github.com/sun-zihang/wallpaper-forge/releases";

export function mountDesktop(root) {
  root.innerHTML = `
    <div class="page-head">
      <h1>桌面版</h1>
      <p>Web 版很好，但桌面版更强。同一套转换能力，加上无大小限制、GPU 加速与一键导入 Wallpaper Engine。</p>
    </div>
    <div class="panel">
      <p class="panel-title">Web 版 vs 桌面版</p>
      <table class="compare">
        <thead>
          <tr><th></th><th>Web 版</th><th>桌面版</th></tr>
        </thead>
        <tbody>
          <tr><td>单文件体积</td><td class="no">≤ 100MB</td><td class="yes">无限制</td></tr>
          <tr><td>视频时长</td><td class="no">≤ 300 秒</td><td class="yes">无限制</td></tr>
          <tr><td>去水印</td><td class="no">不支持</td><td class="yes">图片修复 / 视频 delogo</td></tr>
          <tr><td>GPU 硬件加速</td><td class="no">—</td><td class="yes">支持</td></tr>
          <tr><td>一键导入 Wallpaper Engine</td><td class="no">—</td><td class="yes">支持</td></tr>
          <tr><td>批量自动作业 / 项目回包</td><td class="no">—</td><td class="yes">支持</td></tr>
          <tr><td>免安装 / 文件不上传</td><td class="yes">✓</td><td class="no">—</td></tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <p class="panel-title">桌面版独占能力</p>
      <div class="row">
        <div class="card"><b>GPU 硬件加速</b><small>同一视频 Web 版数分钟，桌面版数十秒完成。</small></div>
        <div class="card"><b>一键导入 WE</b><small>处理好的壁纸直接导入 Wallpaper Engine，三步变一步。</small></div>
        <div class="card"><b>智能去水印</b><small>图片修复与视频 delogo，水印被智能抹除。</small></div>
      </div>
    </div>
    <div class="panel">
      <p class="panel-title">下载</p>
      <div class="row">
        <a class="btn" href="${RELEASES_URL}" target="_blank" rel="noopener">下载 Windows 版</a>
        <span class="drop-hint">免费使用，无广告，无捆绑。安装包约 80MB，附 SHA256 校验。</span>
      </div>
    </div>
  `;

  const dlBtn = root.querySelector('a.btn[href*="releases"]');
  if (dlBtn) dlBtn.addEventListener("click", () => trackDesktop("download"));

  registerShortcutAction("onOpen", () => {});
  registerShortcutAction("onStart", () => {});
  registerShortcutAction("onDownload", () => {});
  registerShortcutAction("onCancel", () => {});
}
