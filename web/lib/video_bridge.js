// web/lib/video_bridge.js
import { AppError } from "./errors.js";

const FFMPEG_URL = "https://cdn.jsdelivr.net/npm/@ffmpeg/ffmpeg@0.12.10/dist/umd/ffmpeg.js";
const UTIL_URL = "https://cdn.jsdelivr.net/npm/@ffmpeg/util@0.12.1/dist/umd/index.js";
const CORE_BASE = "https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.6/dist/umd";

let loadPromise = null;
let ffmpeg = null;

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload = () => resolve();
    s.onerror = () => reject(new AppError("视频处理失败", `无法加载依赖: ${src}`));
    document.head.appendChild(s);
  });
}

export async function ensureFFmpeg(onStatus) {
  if (ffmpeg) return ffmpeg;
  if (!loadPromise) {
    loadPromise = (async () => {
      if (onStatus) onStatus("正在加载视频引擎…");
      await loadScript(UTIL_URL);
      await loadScript(FFMPEG_URL);
      const { FFmpeg } = globalThis.FFmpegWASM;
      const { toBlobURL } = globalThis.FFmpegUtil;
      const inst = new FFmpeg();
      if (onStatus) onStatus("正在下载核心（可能需数 MB）…");
      await inst.load({
        coreURL: await toBlobURL(`${CORE_BASE}/ffmpeg-core.js`, "text/javascript"),
        wasmURL: await toBlobURL(`${CORE_BASE}/ffmpeg-core.wasm`, "application/wasm"),
      });
      ffmpeg = inst;
      return inst;
    })().catch((e) => {
      loadPromise = null;
      throw e instanceof AppError ? e : new AppError("视频处理失败", String(e));
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
