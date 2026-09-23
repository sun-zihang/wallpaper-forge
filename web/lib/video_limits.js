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
