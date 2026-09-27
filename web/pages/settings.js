// web/pages/settings.js
import { setStatus, getRenderToken } from "../app.js";
import { DEFAULT_SETTINGS, loadSettings, saveSettings, applyTheme } from "../lib/settings.js";

export function mountSettings(root) {
  const pageToken = getRenderToken();
  const s = loadSettings();
  root.innerHTML = `
    <div class="page-head">
      <h1>设置</h1>
      <p>偏好保存在浏览器本地，不会上传。</p>
    </div>
    <div class="panel">
      <p class="panel-title">外观</p>
      <div class="row">
        <div class="field">
          <label for="theme">主题</label>
          <select id="theme">
            <option value="dark">暗色</option>
            <option value="light">亮色</option>
            <option value="system">跟随系统</option>
          </select>
        </div>
      </div>
    </div>
    <div class="panel">
      <p class="panel-title">默认参数</p>
      <div class="row">
        <div class="field">
          <label for="imageFormat">图片默认格式</label>
          <select id="imageFormat">
            <option>PNG</option>
            <option>JPG</option>
            <option>WebP</option>
            <option>BMP</option>
            <option>GIF</option>
          </select>
        </div>
        <div class="field">
          <label for="imageQuality">图片默认质量 <span id="imageQuality_v">${s.imageQuality}</span></label>
          <input type="range" id="imageQuality" min="1" max="100" value="${s.imageQuality}" />
        </div>
        <div class="field">
          <label for="imageWidth">图片默认宽度</label>
          <input type="number" id="imageWidth" min="16" max="8192" value="${s.imageWidth}" />
        </div>
      </div>
      <div class="row">
        <div class="field">
          <label for="videoFormat">视频默认格式</label>
          <select id="videoFormat">
            <option value="mp4">MP4</option>
            <option value="webm">WebM</option>
          </select>
        </div>
        <div class="field">
          <label for="videoCrf">视频默认 CRF <span id="videoCrf_v">${s.videoCrf}</span></label>
          <input type="range" id="videoCrf" min="0" max="51" value="${s.videoCrf}" />
        </div>
        <div class="field">
          <label for="gifStep">GIF 默认抽稀步长</label>
          <input type="number" id="gifStep" min="1" max="30" value="${s.gifStep}" />
        </div>
      </div>
    </div>
    <div class="panel">
      <p class="panel-title">性能</p>
      <div class="row">
        <div class="field">
          <label for="memoryLimitMb">内存警告阈值 (MB)</label>
          <select id="memoryLimitMb">
            <option value="1000">1GB</option>
            <option value="1500">1.5GB</option>
            <option value="2000">2GB</option>
          </select>
        </div>
      </div>
    </div>
    <div class="panel">
      <p class="panel-title">存储</p>
      <div class="row">
        <span class="drop-hint" id="cacheUsage">缓存占用：计算中…</span>
        <button type="button" class="btn secondary" id="clearCache">清除所有缓存</button>
      </div>
    </div>
    <pre class="err" id="err"></pre>
  `;
  const $ = (id) => root.querySelector(`#${id}`);
  const err = $("err");

  $("theme").value = s.theme;
  $("imageFormat").value = s.imageFormat;
  $("videoFormat").value = s.videoFormat;
  $("memoryLimitMb").value = String(s.memoryLimitMb);

  $("theme").addEventListener("change", () => {
    const next = saveSettings({ theme: $("theme").value });
    applyTheme(next.theme);
  });
  $("imageFormat").addEventListener("change", () => saveSettings({ imageFormat: $("imageFormat").value }));
  $("imageQuality").addEventListener("input", () => {
    $("imageQuality_v").textContent = $("imageQuality").value;
    saveSettings({ imageQuality: Number($("imageQuality").value) });
  });
  $("imageWidth").addEventListener("change", () => saveSettings({ imageWidth: Number($("imageWidth").value) }));
  $("videoFormat").addEventListener("change", () => saveSettings({ videoFormat: $("videoFormat").value }));
  $("videoCrf").addEventListener("input", () => {
    $("videoCrf_v").textContent = $("videoCrf").value;
    saveSettings({ videoCrf: Number($("videoCrf").value) });
  });
  $("gifStep").addEventListener("change", () => saveSettings({ gifStep: Number($("gifStep").value) }));
  $("memoryLimitMb").addEventListener("change", () => saveSettings({ memoryLimitMb: Number($("memoryLimitMb").value) }));

  applyTheme(s.theme);

  async function refreshUsage() {
    if (pageToken !== getRenderToken()) return;
    try {
      if (navigator.storage && navigator.storage.estimate) {
        const est = await navigator.storage.estimate();
        const mb = Math.round((est.usage || 0) / 1024 / 1024);
        $("cacheUsage").textContent = `缓存占用：约 ${mb}MB`;
      } else {
        $("cacheUsage").textContent = "当前浏览器不支持存储估算";
      }
    } catch {
      $("cacheUsage").textContent = "缓存占用：无法计算";
    }
  }
  refreshUsage();

  $("clearCache").addEventListener("click", async () => {
    if (pageToken !== getRenderToken()) return;
    err.textContent = "";
    try {
      if (typeof caches !== "undefined" && caches.keys) {
        const keys = await caches.keys();
        for (const k of keys) await caches.delete(k);
      }
      try {
        localStorage.removeItem("wc.fmt");
        localStorage.removeItem("wc.q");
      } catch { /* ignore */ }
      setStatus("缓存已清除");
      refreshUsage();
    } catch (e) {
      err.textContent = `清除失败：${e && e.message ? e.message : e}`;
    }
  });
}
