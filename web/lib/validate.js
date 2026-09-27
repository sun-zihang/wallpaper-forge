// web/lib/validate.js
// 文件头（magic bytes）校验与极端分辨率防护。
// 浏览器端无法像桌面版那样用 ffprobe 预检，因此在解码/转码前用文件头
// 剔除伪装文件与畸形尺寸，给出可操作的中文错误而不是让解码器崩溃。
import { AppError } from "./errors.js";

export const MAX_IMAGE_DIM = 16384;
const MAX_HEADER_DIM = 100_000;

const PNG_MAGIC = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
const JPEG_MAGIC = [0xff, 0xd8, 0xff];
const GIF_MAGIC = [0x47, 0x49, 0x46, 0x38];
const BMP_MAGIC = [0x42, 0x4d];
const RIFF_MAGIC = [0x52, 0x49, 0x46, 0x46];
const WEBP_TAG = [0x57, 0x45, 0x42, 0x50];
const EBML_MAGIC = [0x1a, 0x45, 0xdf, 0xa3];

function matches(bytes, offset, magic) {
  if (bytes.length < offset + magic.length) return false;
  for (let i = 0; i < magic.length; i++) {
    if (bytes[offset + i] !== magic[i]) return false;
  }
  return true;
}

function readUint32BE(bytes, offset) {
  return ((bytes[offset] << 24) | (bytes[offset + 1] << 16) | (bytes[offset + 2] << 8) | bytes[offset + 3]) >>> 0;
}

/** 识别图片类型：png / jpeg / gif / bmp / webp，无法识别返回 null。 */
export function sniffImage(bytes) {
  if (matches(bytes, 0, PNG_MAGIC)) return "png";
  if (matches(bytes, 0, JPEG_MAGIC)) return "jpeg";
  if (matches(bytes, 0, GIF_MAGIC)) return "gif";
  if (matches(bytes, 0, BMP_MAGIC)) return "bmp";
  if (matches(bytes, 0, RIFF_MAGIC) && matches(bytes, 8, WEBP_TAG)) return "webp";
  return null;
}

/** 从 PNG IHDR 读取声明尺寸（偏移 16/20，大端）。非 PNG 返回 null。 */
export function pngHeaderSize(bytes) {
  if (sniffImage(bytes) !== "png" || bytes.length < 24) return null;
  return { width: readUint32BE(bytes, 16), height: readUint32BE(bytes, 20) };
}

/**
 * 校验图片文件头。拒绝无法识别的类型与声明尺寸明显畸形的 PNG
 * （如 width = 9999999 的畸形文件头）。
 */
export function validateImageBytes(bytes, name = "") {
  const kind = sniffImage(bytes);
  if (!kind) {
    throw new AppError("图片处理失败", `文件头无法识别为图片: ${name || "未知文件"}`);
  }
  if (kind === "png") {
    const size = pngHeaderSize(bytes);
    if (size && (size.width <= 0 || size.height <= 0 || size.width > MAX_HEADER_DIM || size.height > MAX_HEADER_DIM)) {
      throw new AppError("图片处理失败", `图片尺寸异常: ${size.width}×${size.height}`);
    }
  }
  return kind;
}

/** 读取文件头部若干字节并校验图片文件头。 */
export async function validateImageFile(file, { bytes = 32 } = {}) {
  const buf = new Uint8Array(await file.slice(0, bytes).arrayBuffer());
  return validateImageBytes(buf, file && file.name);
}

/**
 * 解码后的位图尺寸防护：超过 16384×16384 的图片在 Web 端处理可能导致
 * 浏览器崩溃，引导用户使用桌面版。
 */
export function assertImageResolution(width, height) {
  if (width > MAX_IMAGE_DIM || height > MAX_IMAGE_DIM) {
    throw new AppError(
      "图片处理失败",
      `该图片分辨率过高（${width}×${height}），Web 端处理可能导致浏览器崩溃。建议下载桌面版处理。`,
    );
  }
}

/** 识别视频容器：ISO-BMFF（ftyp，mp4/mov）或 EBML（webm/mkv）。 */
export function sniffVideo(bytes) {
  if (bytes.length >= 12 && matches(bytes, 4, [0x66, 0x74, 0x79, 0x70])) return "bmff";
  if (matches(bytes, 0, EBML_MAGIC)) return "ebml";
  return null;
}

/** 校验视频文件头，拒绝非视频容器。 */
export function validateVideoBytes(bytes, name = "") {
  const kind = sniffVideo(bytes);
  if (!kind) {
    throw new AppError("视频处理失败", `文件头无法识别为视频: ${name || "未知文件"}`);
  }
  return kind;
}

/** 读取文件头部若干字节并校验视频文件头。 */
export async function validateVideoFile(file, { bytes = 16 } = {}) {
  const buf = new Uint8Array(await file.slice(0, bytes).arrayBuffer());
  return validateVideoBytes(buf, file && file.name);
}
