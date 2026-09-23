import { AppError } from "./errors.js";

const label = "TEX 解析失败";
const PNG_SIG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

function findSub(hay, needle, from = 0) {
  // needle: number[]
  outer: for (let i = from; i <= hay.length - needle.length; i++) {
    for (let j = 0; j < needle.length; j++) if (hay[i + j] !== needle[j]) continue outer;
    return i;
  }
  return -1;
}

function u32le(data, i) {
  return (data[i] | (data[i + 1] << 8) | (data[i + 2] << 16) | (data[i + 3] << 24)) >>> 0;
}

function u32be(data, i) {
  return ((data[i] << 24) | (data[i + 1] << 16) | (data[i + 2] << 8) | data[i + 3]) >>> 0;
}

export function extractEmbedded(texData) {
  const candidates = [];
  // PNG
  let idx = 0;
  while (true) {
    const i = findSub(texData, PNG_SIG, idx);
    if (i < 0) break;
    let end = texData.length;
    if (i >= 4) {
      const ln = u32le(texData, i - 4);
      if (ln >= 8 && i + ln <= texData.length) end = i + ln;
    }
    candidates.push({ ext: ".png", start: i, end });
    idx = i + 1;
  }
  // JPEG SOI
  const j = findSub(texData, [0xff, 0xd8, 0xff]);
  if (j >= 0) {
    let end = texData.length;
    if (j >= 4) {
      const ln = u32le(texData, j - 4);
      if (ln >= 16 && j + ln <= texData.length) end = j + ln;
    }
    const eoi = findSub(texData, [0xff, 0xd9], j);
    if (eoi !== -1 && eoi + 2 <= end) end = eoi + 2;
    candidates.push({ ext: ".jpg", start: j, end });
  }
  // WebP
  idx = 0;
  while (true) {
    const i = findSub(texData, [0x57, 0x45, 0x42, 0x50], idx); // WEBP
    if (i < 0) break;
    if (i >= 4 && texData[i - 8] === 0x52 && texData[i - 7] === 0x49 && texData[i - 6] === 0x46 && texData[i - 5] === 0x46) {
      const riff = i - 8;
      const size = u32le(texData, riff + 4) + 8;
      if (riff + size <= texData.length) candidates.push({ ext: ".webp", start: riff, end: riff + size });
    }
    idx = i + 1;
  }
  // MP4
  const ftyp = [0x66, 0x74, 0x79, 0x70];
  idx = 0;
  while (true) {
    const i = findSub(texData, ftyp, idx);
    if (i < 0) break;
    if (i >= 4) {
      const boxSize = u32be(texData, i - 4);
      const start = i - 4;
      if (boxSize >= 8 && boxSize <= texData.length - start) {
        candidates.push({ ext: ".mp4", start, end: start + boxSize });
      } else {
        candidates.push({ ext: ".mp4", start, end: texData.length });
      }
    }
    idx = i + 1;
  }
  if (!candidates.length) return { ext: null, payload: null };
  const priority = { ".mp4": 0, ".png": 1, ".webp": 2, ".jpg": 3 };
  candidates.sort((a, b) => (priority[a.ext] ?? 9) - (priority[b.ext] ?? 9) || (b.end - b.start) - (a.end - a.start));
  const c = candidates[0];
  const payload = texData.slice(c.start, c.end);
  if (payload.length < 16) return { ext: null, payload: null };
  return { ext: c.ext, payload };
}

export function extractTex(texData, baseName) {
  const { ext, payload } = extractEmbedded(texData);
  if (ext && payload) {
    return { name: `${baseName}${ext}`, blob: payload };
  }
  return { name: `${baseName}.tex`, blob: texData };
}
