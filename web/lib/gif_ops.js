// web/lib/gif_ops.js
import { AppError } from "./errors.js";

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

export const GIFUCT_ESM_URL = "https://cdn.jsdelivr.net/npm/gifuct-js@2.1.2/+esm";

const modulePromises = new Map();

export function ensureGifuct() {
  if (!modulePromises.has(GIFUCT_ESM_URL)) {
    const p = import(GIFUCT_ESM_URL).catch(() => {
      modulePromises.delete(GIFUCT_ESM_URL);
      throw new AppError("GIF 处理失败", `无法加载依赖: ${GIFUCT_ESM_URL}`);
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
  const frames = [];
  let width = 0;
  let height = 0;
  for (const frame of parsed.frames) {
    throwIfCancelled(token);
    const patch = decompressFramePatch(lib, parsed, frame);
    if (!patch) continue;
    width = width || parsed.lsd.width;
    height = height || parsed.lsd.height;
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    const img = ctx.createImageData(width, height);
    img.data.set(patch.patch);
    ctx.putImageData(img, 0, 0);
    frames.push(canvas);
  }
  if (!frames.length) throw new AppError("GIF 处理失败", "GIF 中没有可导出的帧");
  return { width: width || frames[0].width, height: height || frames[0].height, frames };
}

export async function splitGif(file, { step = 1, token } = {}) {
  if (step < 1) throw new AppError("GIF 处理失败", "抽稀步长至少为 1");
  const { frames } = await loadGifFrames(file, { token });
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

export async function mergeGif(files, { durationMs = 100, loop = 0, reverse = false, token } = {}) {
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
  const blob = encodeAnimatedGif(canvases, { durationMs, loop });
  const first = ordered[0];
  const base = (first.name || "out").replace(/\.[^.]+$/, "");
  return { blob, filename: `${base}.gif` };
}

/** Minimal GIF89a animated writer (RGBA frames, global palette = median-cut simplified to 6x6x6 web-safe). */
export function encodeAnimatedGif(canvases, { durationMs = 100, loop = 0 } = {}) {
  if (!canvases.length) throw new AppError("GIF 处理失败", "没有可合并的图片");
  const w = canvases[0].width;
  const h = canvases[0].height;
  const framesData = canvases.map((c) => c.getContext("2d").getImageData(0, 0, w, h).data);
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
  for (const data of framesData) {
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
  }
  out.push(0x3b);
  return new Blob([new Uint8Array(out)], { type: "image/gif" });
}

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

function mapToPalette(data, palette) {
  const idx = new Uint8Array((data.length / 4) | 0);
  for (let p = 0, i = 0; i < data.length; i += 4, p++) {
    const r = data[i], g = data[i + 1], b = data[i + 2];
    let best = 0, bestD = Infinity;
    for (let k = 0; k < palette.length; k++) {
      const pr = palette[k][0] - r, pg = palette[k][1] - g, pb = palette[k][2] - b;
      const d = pr * pr + pg * pg + pb * pb;
      if (d < bestD) { bestD = d; best = k; }
    }
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
