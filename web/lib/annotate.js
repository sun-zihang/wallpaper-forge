import { AppError } from "./errors.js";
import { loadImageBitmap } from "./image_ops.js";

export const POSITIONS = [
  "top_left",
  "top_right",
  "bottom_left",
  "bottom_right",
  "center",
];

export function cropBoxValid(box, w, h) {
  const [l, t, r, b] = box;
  return Number.isFinite(l) && Number.isFinite(t) && Number.isFinite(r) && Number.isFinite(b)
    && 0 <= l && l < r && r <= w && 0 <= t && t < b && b <= h;
}

export function cropCanvas(src, box) {
  const [l, t, r, b] = box;
  if (!cropBoxValid(box, src.width, src.height)) {
    throw new AppError("图片处理失败", `裁剪区域无效: 必须在 0..${src.width} × 0..${src.height} 范围内`);
  }
  const out = document.createElement("canvas");
  out.width = r - l;
  out.height = b - t;
  out.getContext("2d").drawImage(src, l, t, r - l, b - t, 0, 0, out.width, out.height);
  return out;
}

export function pastePos(cw, ch, mw, mh, position, margin = 16) {
  if (!POSITIONS.includes(position)) {
    throw new AppError("图片处理失败", `未知水印位置: ${position}`);
  }
  if (position === "top_left") return [margin, margin];
  if (position === "top_right") return [cw - mw - margin, margin];
  if (position === "bottom_left") return [margin, ch - mh - margin];
  if (position === "bottom_right") return [cw - mw - margin, ch - mh - margin];
  return [(cw - mw) >> 1, (ch - mh) >> 1];
}

export async function addTextWatermark(file, { text, fontSize = 32, color = "rgba(255,255,255,0.7)", position = "bottom_right", margin = 16 } = {}) {
  if (!text) throw new AppError("图片处理失败", "水印文字不能为空");
  const bitmap = await loadImageBitmap(file);
  const canvas = document.createElement("canvas");
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(bitmap, 0, 0);
  bitmap.close && bitmap.close();
  ctx.font = `${fontSize}px sans-serif`;
  ctx.fillStyle = color;
  ctx.textBaseline = "top";
  const m = ctx.measureText(text);
  const tw = m.width;
  const th = fontSize * 1.2;
  const [x, y] = pastePos(canvas.width, canvas.height, tw, th, position, margin);
  ctx.fillText(text, x, y);
  const blob = await new Promise((res, rej) => canvas.toBlob((b) => (b ? res(b) : rej(new AppError("图片处理失败", "保存失败"))), "image/png"));
  return { blob, filename: (file.name || "image").replace(/\.[^.]+$/, "") + "_wm.png" };
}

export async function addImageWatermark(file, markFile, { scale = 0.2, position = "bottom_right", margin = 16, opacity = 0.8 } = {}) {
  if (!(scale >= 0.05 && scale <= 1)) throw new AppError("图片处理失败", "水印缩放比例需在 0.05–1.0 之间");
  if (!(opacity >= 0 && opacity <= 1)) throw new AppError("图片处理失败", "透明度需在 0–1 之间");
  const base = await loadImageBitmap(file);
  const mark = await loadImageBitmap(markFile);
  const canvas = document.createElement("canvas");
  canvas.width = base.width;
  canvas.height = base.height;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(base, 0, 0);
  const mw = Math.max(1, Math.round(base.width * scale));
  const mh = Math.max(1, Math.round(mark.height * (mw / mark.width)));
  const off = document.createElement("canvas");
  off.width = mw;
  off.height = mh;
  const octx = off.getContext("2d");
  octx.globalAlpha = opacity;
  octx.drawImage(mark, 0, 0, mw, mh);
  const [x, y] = pastePos(canvas.width, canvas.height, mw, mh, position, margin);
  ctx.drawImage(off, x, y);
  base.close && base.close();
  mark.close && mark.close();
  const blob = await new Promise((res, rej) => canvas.toBlob((b) => (b ? res(b) : rej(new AppError("图片处理失败", "保存失败"))), "image/png"));
  return { blob, filename: (file.name || "image").replace(/\.[^.]+$/, "") + "_wm.png" };
}
