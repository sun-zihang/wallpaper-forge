// web/lib/video_limits.js
import { AppError } from "./errors.js";

export const MAX_VIDEO_BYTES = 100 * 1024 * 1024;
export const MAX_VIDEO_SECONDS = 300;

export function assertVideoLimits(fileLike) {
  const size = fileLike.size ?? 0;
  if (size > MAX_VIDEO_BYTES) {
    throw new AppError("视频处理失败", `单文件超过 ${Math.round(MAX_VIDEO_BYTES / 1024 / 1024)}MB 上限，请使用桌面版`);
  }
  const sec = fileLike.durationSec;
  if (sec != null && sec > MAX_VIDEO_SECONDS) {
    throw new AppError("视频处理失败", `时长超过 ${MAX_VIDEO_SECONDS} 秒上限，请使用桌面版`);
  }
}

export function durationTooLongError() {
  return new AppError("视频处理失败", `时长超过 ${MAX_VIDEO_SECONDS} 秒上限，请使用桌面版`);
}

/** Probe duration via DOM <video> metadata. Resolves seconds if finite, else null (~5s timeout). */
export function probeVideoDuration(file) {
  return new Promise((resolve) => {
    if (typeof document === "undefined" || typeof URL === "undefined" || !URL.createObjectURL) {
      resolve(null);
      return;
    }
    const url = URL.createObjectURL(file);
    const v = document.createElement("video");
    v.preload = "metadata";
    let settled = false;
    const finish = (val) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      v.onloadedmetadata = null;
      v.onerror = null;
      try {
        v.removeAttribute("src");
        v.load();
      } catch { /* ignore */ }
      try {
        URL.revokeObjectURL(url);
      } catch { /* ignore */ }
      resolve(val);
    };
    const timer = setTimeout(() => finish(null), 5000);
    v.onloadedmetadata = () => {
      const d = v.duration;
      finish(typeof d === "number" && Number.isFinite(d) && d > 0 ? d : null);
    };
    v.onerror = () => finish(null);
    v.src = url;
  });
}
