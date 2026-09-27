// Canvas seam for dual-context execution: module workers have OffscreenCanvas
// but no document, while the main thread and the node tests build canvases via
// document.createElement (tests stub it on globalThis).
import { AppError } from "./errors.js";

export function createCanvas(w, h) {
  if (typeof document !== "undefined") {
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    return c;
  }
  if (typeof OffscreenCanvas !== "undefined") {
    return new OffscreenCanvas(w, h);
  }
  throw new Error("no canvas implementation available in this context");
}

export async function encodeCanvas(canvas, type, quality, label) {
  if (typeof canvas.toBlob === "function") {
    return await new Promise((resolve, reject) => {
      canvas.toBlob((b) => (b ? resolve(b) : reject(new AppError(label, "保存失败"))), type, quality);
    });
  }
  try {
    return await canvas.convertToBlob({ type, quality });
  } catch (e) {
    throw new AppError(label, `保存失败: ${e && e.message ? e.message : e}`);
  }
}
