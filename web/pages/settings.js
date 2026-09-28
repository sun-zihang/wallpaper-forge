// web/pages/settings.js
import { setStatus, getRenderToken } from "../app.js";
import { DEFAULT_SETTINGS, loadSettings, saveSettings, applyTheme } from "../lib/settings.js";
import { clearStats, getStats } from "../lib/track.js";
import { isEnabled, setEnabled, getEndpoint, flush } from "../lib/telemetry.js";

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
    <div class="panel">
      <p class="panel-title">本地使用统计</p>
      <p class="drop-hint">计数默认只保存在这台浏览器里，不上传。用于了解功能使用情况与失败原因；如愿意，可在下方选择开启匿名统计。</p>
      <pre class="stats-summary" id="statsSummary">统计中…</pre>
      <pre class="stats-detail" id="statsDetail"></pre>
      <div class="row">
        <button type="button" class="btn secondary" id="clearStats">清除统计</button>
      </div>
    </div>
    <div class="panel">
      <p class="panel-title">匿名统计（可选，默认关闭）</p>
      <p class="drop-hint">开启后，仅在页面关闭时发送上面的聚合计数：不含文件名、不含事件明细、不含任何文件内容。</p>
      <div class="row">
        <label class="drop-hint"><input type="checkbox" id="telemetryOptIn" /> 发送匿名聚合计数</label>
        <span class="drop-hint" id="telemetryStatus"></span>
        <button type="button" class="btn secondary" id="telemetrySend">立即发送</button>
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

  function renderStats() {
    if (pageToken !== getRenderToken()) return;
    const st = getStats();
    if (!st.total) {
      $("statsSummary").textContent = "还没有统计数据。处理几个文件后这里会显示使用情况。";
      $("statsDetail").textContent = "";
      return;
    }
    const pct = (x) => `${Math.round(x * 100)}%`;
    const fmt = (obj) =>
      Object.entries(obj)
        .sort((a, b) => b[1] - a[1])
        .map(([k, n]) => `${k} ${n}`)
        .join("、");
    $("statsSummary").textContent = [
      `模块点击：${fmt(st.modules) || "无"}`,
      `上传未开始率：${pct(st.uploadsNotStarted)}（上传 ${st.added} 次 / 开始 ${st.starts} 次）`,
      `平均任务耗时：${st.avgMs ? `${(st.avgMs / 1000).toFixed(1)} 秒` : "无"}（${st.runs} 次完成）`,
      `放弃率：${pct(st.abandonRate)}（任务中离开 ${st.abandoned} 次）`,
      `失败类型：${fmt(st.failures) || "无"}`,
      `桌面版下载点击：${st.desktop}`,
    ].join("\n");
    $("statsDetail").textContent = JSON.stringify(st.counters, null, 2);
  }
  renderStats();
  $("clearStats").addEventListener("click", () => {
    if (pageToken !== getRenderToken()) return;
    clearStats();
    renderStats();
    setStatus("统计数据已清除");
  });

  const opt = $("telemetryOptIn");
  opt.checked = isEnabled();
  const renderTelemetry = () => {
    $("telemetryStatus").textContent = getEndpoint()
      ? isEnabled()
        ? "已开启 · 端点已配置"
        : "已关闭 · 端点已配置"
      : "端点未配置：开启后暂不会发送";
  };
  renderTelemetry();
  opt.addEventListener("change", () => {
    setEnabled(opt.checked);
    renderTelemetry();
    setStatus(opt.checked ? "已开启匿名统计" : "已关闭匿名统计");
  });
  $("telemetrySend").addEventListener("click", async () => {
    if (pageToken !== getRenderToken()) return;
    const r = await flush({ force: true });
    setStatus(r.sent ? "匿名统计已发送" : `未发送（${r.reason}）`);
  });

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
