// web/lib/gif_ops.js
import { AppError } from "./errors.js";
import { GIFUCT_URLS, importFirst } from "./cdn.js";

export function stepIndexKept(index, step) {
  return index % Math.max(1, step | 0) === 0;
}

export function mergeOrder(list, reverse) {
  const arr = [...list];
  return reverse ? arr.reverse() : arr;
}

function throwIfCancelled(token) {
  if (token && token.cancelled) throw new AppError("GIF 处理失败", "已取消");
}

export const GIFUCT_ESM_URL = GIFUCT_URLS[0];

const modulePromises = new Map();

export function ensureGifuct() {
  if (!modulePromises.has(GIFUCT_ESM_URL)) {
    const p = importFirst(GIFUCT_URLS).catch(() => {
      modulePromises.delete(GIFUCT_ESM_URL);
      throw new AppError("GIF 处理失败", `无法加载依赖: ${GIFUCT_URLS.join(" / ")}`);
    });
    modulePromises.set(GIFUCT_ESM_URL, p);
  }
  return modulePromises.get(GIFUCT_ESM_URL);
}

export function decompressFramePatch(lib, parsed, frame) {
  const patch = lib.decompressFrame(frame, parsed.gct, true);
  return patch && patch.patch ? patch : null;
}

export async function loadGifFrames(file, { token, gifuct } = {}) {
  const lib = gifuct || (await ensureGifuct());
  if (typeof lib.parseGIF !== "function" || typeof lib.decompressFrame !== "function") {
    throw new AppError("GIF 处理失败", "gifuct 加载失败");
  }
  const buf = await file.arrayBuffer();
  let parsed;
  try {
    parsed = lib.parseGIF(buf);
  } catch (e) {
    throw new AppError("GIF 处理失败", `无法读取 GIF: ${file.name}（${e}）`);
  }
  const width = parsed.lsd.width;
  const height = parsed.lsd.height;
  const buffer = new Uint8ClampedArray(width * height * 4);
  const frames = [];
  for (const frame of parsed.frames) {
    throwIfCancelled(token);
    const patch = decompressFramePatch(lib, parsed, frame);
    if (!patch) continue;
    compositeInto(buffer, width, height, patch);
    frames.push(canvasFromBuffer(buffer, width, height));
    applyDisposal(buffer, width, height, patch, patch.disposalType);
  }
  if (!frames.length) throw new AppError("GIF 处理失败", "GIF 中没有可导出的帧");
  return { width, height, frames };
}

export function compositeInto(buffer, bufW, bufH, patch) {
  const dims = patch.dims || { top: 0, left: 0, width: bufW, height: bufH };
  const src = patch.patch;
  const w = Math.min(dims.width, bufW);
  const h = Math.min(dims.height, bufH);
  for (let y = 0; y < h; y++) {
    const dy = dims.top + y;
    if (dy < 0 || dy >= bufH) continue;
    for (let x = 0; x < w; x++) {
      const dx = dims.left + x;
      if (dx < 0 || dx >= bufW) continue;
      const si = (y * dims.width + x) * 4;
      if (src[si + 3] === 0) continue;
      const di = (dy * bufW + dx) * 4;
      buffer[di] = src[si];
      buffer[di + 1] = src[si + 1];
      buffer[di + 2] = src[si + 2];
      buffer[di + 3] = src[si + 3];
    }
  }
}

export function applyDisposal(buffer, bufW, bufH, patch, disposalType) {
  if (disposalType !== 2) return;
  const dims = patch.dims || { top: 0, left: 0, width: bufW, height: bufH };
  const w = Math.min(dims.width, bufW);
  const h = Math.min(dims.height, bufH);
  for (let y = 0; y < h; y++) {
    const dy = dims.top + y;
    if (dy < 0 || dy >= bufH) continue;
    for (let x = 0; x < w; x++) {
      const dx = dims.left + x;
      if (dx < 0 || dx >= bufW) continue;
      const di = (dy * bufW + dx) * 4;
      buffer[di] = 0;
      buffer[di + 1] = 0;
      buffer[di + 2] = 0;
      buffer[di + 3] = 0;
    }
  }
}

function canvasFromBuffer(buffer, width, height) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  const img = ctx.createImageData(width, height);
  img.data.set(buffer);
  ctx.putImageData(img, 0, 0);
  return canvas;
}

export async function splitGif(file, { step = 1, token, gifuct } = {}) {
  if (step < 1) throw new AppError("GIF 处理失败", "抽稀步长至少为 1");
  const { frames } = await loadGifFrames(file, { token, gifuct });
  const base = (file.name || "a.gif").replace(/\.gif$/i, "");
  const files = [];
  let kept = 0;
  for (let i = 0; i < frames.length; i++) {
    throwIfCancelled(token);
    if (!stepIndexKept(i, step)) continue;
    kept += 1;
    const blob = await new Promise((res, rej) =>
      frames[i].toBlob((b) => (b ? res(b) : rej(new AppError("GIF 处理失败", "保存失败"))), "image/png")
    );
    files.push({ name: `${base}/frame_${String(kept).padStart(4, "0")}.png`, blob });
  }
  if (!files.length) throw new AppError("GIF 处理失败", "GIF 中没有可导出的帧");
  return { files };
}

export async function mergeGif(files, { durationMs = 100, loop = 0, reverse = false, token, onProgress } = {}) {
  if (!files.length) throw new AppError("GIF 处理失败", "没有可合并的图片");
  if (durationMs < 10) throw new AppError("GIF 处理失败", "帧间隔至少 10 毫秒");
  const ordered = mergeOrder(files, reverse);
  const canvases = [];
  for (const f of ordered) {
    throwIfCancelled(token);
    const bmp = await createImageBitmap(f);
    const c = document.createElement("canvas");
    c.width = bmp.width;
    c.height = bmp.height;
    c.getContext("2d").drawImage(bmp, 0, 0);
    bmp.close && bmp.close();
    canvases.push(c);
  }
  const blob = await encodeAnimatedGif(canvases, { durationMs, loop, token, onProgress });
  const first = ordered[0];
  const base = (first.name || "out").replace(/\.[^.]+$/, "");
  return { blob, filename: `${base}.gif` };
}

/** Minimal GIF89a animated writer (RGBA frames, global palette = top-256 histogram colors). */
export async function encodeAnimatedGif(
  canvases,
  { durationMs = 100, loop = 0, token, onProgress } = {}
) {
  if (!canvases.length) throw new AppError("GIF 处理失败", "没有可合并的图片");
  const w = canvases[0].width;
  const h = canvases[0].height;
  const framesData = canvases.map((c) => c.getContext("2d").getImageData(0, 0, w, h).data);
  throwIfCancelled(token);
  const palette = buildPalette(framesData);
  const out = [];
  pushStr(out, "GIF89a");
  pushU16(out, w);
  pushU16(out, h);
  out.push(0xf7, 0, 0);
  for (let i = 0; i < 256; i++) {
    const p = palette[i] || [0, 0, 0];
    out.push(p[0], p[1], p[2]);
  }
  pushStr(out, "\x21\xff\x0bNETSCAPE2.0\x03\x01");
  pushU16(out, loop);
  out.push(0);
  const delay = Math.max(2, Math.round(durationMs / 10));
  for (let fi = 0; fi < framesData.length; fi++) {
    throwIfCancelled(token);
    const data = framesData[fi];
    pushStr(out, "\x21\xf9\x04");
    out.push(0, delay & 0xff, (delay >> 8) & 0xff, 0, 0);
    out.push(0x2c);
    pushU16(out, 0);
    pushU16(out, 0);
    pushU16(out, w);
    pushU16(out, h);
    out.push(0);
    const indices = mapToPalette(data, palette);
    const minCodeSize = 8;
    out.push(minCodeSize);
    const lzw = lzwEncode(indices, minCodeSize);
    for (let i = 0; i < lzw.length; i += 255) {
      const chunk = lzw.slice(i, i + 255);
      out.push(chunk.length);
      for (const b of chunk) out.push(b);
    }
    out.push(0);
    if (onProgress) onProgress(fi + 1, framesData.length);
    await yieldTick();
  }
  out.push(0x3b);
  return new Blob([new Uint8Array(out)], { type: "image/gif" });
}

const yieldTick = () => new Promise((resolve) => setTimeout(resolve, 0));

function pushStr(arr, s) {
  for (let i = 0; i < s.length; i++) arr.push(s.charCodeAt(i));
}
function pushU16(arr, v) {
  arr.push(v & 0xff, (v >> 8) & 0xff);
}

function buildPalette(allFrames) {
  const counts = new Map();
  for (const data of allFrames) {
    for (let i = 0; i < data.length; i += 16) {
      const key = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2];
      counts.set(key, (counts.get(key) || 0) + 1);
    }
  }
  const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 256);
  const pal = sorted.map((k) => [(k[0] >> 16) & 255, (k[0] >> 8) & 255, k[0] & 255]);
  while (pal.length < 256) pal.push([0, 0, 0]);
  return pal;
}

const PALETTE_CACHE_LIMIT = 65536;

export function mapToPalette(data, palette) {
  const n = palette.length;
  const pr = new Uint8Array(n);
  const pg = new Uint8Array(n);
  const pb = new Uint8Array(n);
  for (let k = 0; k < n; k++) {
    const c = palette[k];
    pr[k] = c[0];
    pg[k] = c[1];
    pb[k] = c[2];
  }
  const cache = new Map();
  const idx = new Uint8Array((data.length / 4) | 0);
  let p = 0;
  for (let i = 0; i < data.length; i += 4, p++) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];
    const key = (r << 16) | (g << 8) | b;
    const hit = cache.get(key);
    if (hit !== undefined) {
      idx[p] = hit;
      continue;
    }
    let best = 0;
    let bestD = Infinity;
    for (let k = 0; k < n; k++) {
      const dr = pr[k] - r;
      const dg = pg[k] - g;
      const db = pb[k] - b;
      const d = dr * dr + dg * dg + db * db;
      if (d < bestD) {
        bestD = d;
        best = k;
        if (d === 0) break;
      }
    }
    if (cache.size < PALETTE_CACHE_LIMIT) cache.set(key, best);
    idx[p] = best;
  }
  return idx;
}

function lzwEncode(indices, minCodeSize) {
  const clear = 1 << minCodeSize;
  const eoi = clear + 1;
  let codeSize = minCodeSize + 1;
  let dict = new Map();
  let next = eoi + 1;
  let bitBuf = 0;
  let bitCnt = 0;
  const bytes = [];
  function emit(code) {
    bitBuf |= code << bitCnt;
    bitCnt += codeSize;
    while (bitCnt >= 8) {
      bytes.push(bitBuf & 0xff);
      bitBuf >>= 8;
      bitCnt -= 8;
    }
  }
  function resetDict() {
    dict = new Map();
    next = eoi + 1;
    codeSize = minCodeSize + 1;
  }
  emit(clear);
  if (indices.length === 0) {
    emit(eoi);
    if (bitCnt) bytes.push(bitBuf & 0xff);
    return bytes;
  }
  let prefix = indices[0];
  for (let i = 1; i < indices.length; i++) {
    const k = indices[i];
    const key = prefix * 4096 + k;
    if (dict.has(key)) {
      prefix = dict.get(key);
      continue;
    }
    emit(prefix);
    dict.set(key, next);
    next++;
    if (next > (1 << codeSize)) {
      if (codeSize < 12) codeSize++;
      else {
        emit(clear);
        resetDict();
      }
    }
    prefix = k;
  }
  emit(prefix);
  emit(eoi);
  if (bitCnt) bytes.push(bitBuf & 0xff);
  return bytes;
}
