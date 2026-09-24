import { AppError } from "./errors.js";
import { encodeAnimatedGif } from "./gif_ops.js";

export const IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"];
export const OUT_FORMATS = ["PNG", "JPG", "WebP", "BMP", "GIF"];
export const OUT_EXTS = [".png", ".jpg", ".webp", ".bmp", ".gif"];

const MIME = {
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".bmp": "image/bmp",
  ".gif": "image/gif",
};

export function outputExtFor(fmt) {
  const f = String(fmt).toLowerCase();
  if (f === "jpg" || f === "jpeg") return ".jpg";
  if (f === "png") return ".png";
  if (f === "webp") return ".webp";
  if (f === "bmp") return ".bmp";
  if (f === "gif") return ".gif";
  throw new AppError("图片处理失败", `不支持的输出格式: ${fmt}`);
}

export function qualityExts() {
  return new Set([".jpg", ".jpeg", ".webp"]);
}

export async function loadImageBitmap(file) {
  try {
    return await createImageBitmap(file);
  } catch (e) {
    throw new AppError("图片处理失败", `无法读取图片: ${file.name || ""}（${e}）`);
  }
}

function drawScaled(bitmap, maxWidth) {
  let w = bitmap.width;
  let h = bitmap.height;
  if (maxWidth && maxWidth > 0 && w > maxWidth) {
    h = Math.max(1, Math.round(h * (maxWidth / w)));
    w = maxWidth;
  }
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(bitmap, 0, 0, w, h);
  return canvas;
}

export async function convertImage(file, { format, maxWidth = 0, quality = 90 } = {}) {
  const ext = outputExtFor(format || "PNG");
  if (ext === ".bmp") {
    throw new AppError("图片处理失败", "BMP 格式网页版暂不支持，请使用桌面版");
  }
  const bitmap = await loadImageBitmap(file);
  // GIF animation is flattened to first frame (same as desktop convert of .gif source)
  const canvas = drawScaled(bitmap, maxWidth);
  bitmap.close && bitmap.close();
  const outName = (file.name || "image").replace(/\.[^.]+$/, "") + ext;
  if (ext === ".gif") {
    const blob = await encodeAnimatedGif([canvas], { durationMs: 100 });
    return { blob, filename: outName, width: canvas.width, height: canvas.height };
  }
  const mime = MIME[ext];
  const q = Math.max(1, Math.min(100, quality));
  const opts = qualityExts().has(ext) ? { type: mime, quality: q / 100 } : { type: mime };
  const blob = await new Promise((resolve, reject) => {
    canvas.toBlob((b) => (b ? resolve(b) : reject(new AppError("图片处理失败", "保存失败"))), opts.type, opts.quality);
  });
  return { blob, filename: outName, width: canvas.width, height: canvas.height };
}
