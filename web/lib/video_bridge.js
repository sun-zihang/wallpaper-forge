// web/lib/video_bridge.js
import { AppError } from "./errors.js";
import {
  FFMPEG_CORE_JS_URLS,
  FFMPEG_CORE_WASM_URLS,
  FFMPEG_URLS,
  FFMPEG_UTIL_URLS,
  FFMPEG_WORKER_URLS,
  loadScriptFirst,
  toBlobUrlFirst,
} from "./cdn.js";

// ffmpeg 核心约 25MB，首次加载慢。用 Cache Storage 缓存 CDN 响应，
// 重复访问直接命中缓存。仅对 CDN 域名生效，其他 fetch 不受影响。
const WASM_CACHE = "ffmpeg-core-cache-v1";
const CDN_HOST_RE = /^(https?:)?\/\/(cdn\.jsdelivr\.net|unpkg\.com|esm\.sh)\//;

export async function cachedCdnFetch(url, orig, ...args) {
  try {
    const cache = await caches.open(WASM_CACHE);
    const hit = await cache.match(url);
    if (hit) return hit;
    const res = await orig(url, ...args);
    if (res && res.ok) {
      try {
        await cache.put(url, res.clone());
      } catch { /* 配额不足时跳过缓存，不影响功能 */ }
    }
    return res;
  } catch {
    return orig(url, ...args);
  }
}

export function installCachingFetch() {
  if (typeof caches === "undefined" || typeof caches.open !== "function") return;
  const orig = globalThis.fetch;
  if (typeof orig !== "function" || orig.__wcCache) return;
  const wrapped = (url, ...args) => {
    const key = typeof url === "string" ? url : (url && url.url) || "";
    if (!CDN_HOST_RE.test(key)) return orig(url, ...args);
    return cachedCdnFetch(key, orig, ...args);
  };
  wrapped.__wcCache = true;
  globalThis.fetch = wrapped;
}

let loadPromise = null;
let ffmpeg = null;

export async function ensureFFmpeg(onStatus) {
  if (ffmpeg) return ffmpeg;
  if (!loadPromise) {
    loadPromise = (async () => {
      installCachingFetch();
      if (onStatus) onStatus("正在加载视频引擎…");
      await loadScriptFirst(FFMPEG_UTIL_URLS);
      await loadScriptFirst(FFMPEG_URLS);
      const { FFmpeg } = globalThis.FFmpegWASM;
      const { toBlobURL } = globalThis.FFmpegUtil;
      const inst = new FFmpeg();
      if (onStatus) onStatus("正在下载核心（可能需数 MB）…");
      await inst.load({
        coreURL: await toBlobUrlFirst(FFMPEG_CORE_JS_URLS, "text/javascript", toBlobURL),
        wasmURL: await toBlobUrlFirst(FFMPEG_CORE_WASM_URLS, "application/wasm", toBlobURL),
        classWorkerURL: await toBlobUrlFirst(FFMPEG_WORKER_URLS, "text/javascript", toBlobURL),
      });
      ffmpeg = inst;
      return inst;
    })().catch((e) => {
      loadPromise = null;
      throw e instanceof AppError ? e : new AppError("视频处理失败", String(e && e.message ? e.message : e));
    });
  }
  return loadPromise;
}

/**
 * Run one ffmpeg invocation. args exclude binary name.
 * Writes output to virtual FS path `outPath`.
 */
export async function runFFmpeg({ args, outPath, onProgress, cancelToken }) {
  const ff = await ensureFFmpeg((s) => onProgress && onProgress(-1, s));
  if (cancelToken && cancelToken.cancelled) throw new AppError("视频处理失败", "已取消");
  const cancelledError = () => new AppError("视频处理失败", "已取消");
  const progressHandler = ({ progress }) => {
    if (onProgress && progress != null) onProgress(Math.max(0, Math.min(100, Math.round(progress * 100))), null);
  };
  let logTail = "";
  const logHandler = ({ message }) => {
    if (typeof message === "string" && message) {
      logTail = (logTail + message + "\n").slice(-200);
    }
  };
  const unsubProgress = ff.on?.("progress", progressHandler);
  const unsubLog = ff.on?.("log", logHandler);
  let pollTimer = null;
  let terminating = false;
  try {
    if (cancelToken) {
      pollTimer = setInterval(() => {
        if (!cancelToken.cancelled || terminating) return;
        terminating = true;
        clearInterval(pollTimer);
        pollTimer = null;
        (async () => {
          try {
            await ff.terminate();
          } catch { /* best effort */ }
          ffmpeg = null;
          loadPromise = null;
        })();
      }, 200);
    }
    let code;
    try {
      code = await ff.exec(args);
    } catch (e) {
      if (cancelToken && cancelToken.cancelled) throw cancelledError();
      const detail = `${String((e && e.message) || e)}：${logTail.slice(-200)}`;
      throw e instanceof AppError ? e : new AppError("视频处理失败", detail);
    }
    if (cancelToken && cancelToken.cancelled) throw cancelledError();
    if (code !== 0 && code != null) {
      throw new AppError("视频处理失败", `FFmpeg 编码失败（code ${code}）：${logTail.slice(-200)}`);
    }
    if (onProgress) onProgress(100, null);
  } finally {
    if (pollTimer != null) clearInterval(pollTimer);
    if (typeof unsubProgress === "function") unsubProgress();
    else if (typeof ff.off === "function") ff.off("progress", progressHandler);
    if (typeof unsubLog === "function") unsubLog();
    else if (typeof ff.off === "function") ff.off("log", logHandler);
  }
}

export async function writeFileFromBlob(ff, path, blob) {
  const buf = new Uint8Array(await blob.arrayBuffer());
  await ff.writeFile(path, buf);
  return path;
}

export async function readFileToBlob(ff, path) {
  const data = await ff.readFile(path);
  const bytes = data instanceof Uint8Array ? data : new Uint8Array(data);
  const type = path.endsWith(".gif")
    ? "image/gif"
    : path.endsWith(".png")
      ? "image/png"
      : path.endsWith(".webm")
        ? "video/webm"
        : "video/mp4";
  return new Blob([bytes], { type });
}
