import { AppError } from "./errors.js";
import { extractPkg, readPkgIndex } from "./we_pkg.js";
import { extractEmbedded, extractTex } from "./we_tex.js";

const label = "MPKG 解包失败";
const MAGICS = ["PKGM0014", "PKGM0015", "PKGM0016", "PKGM0017", "PKGM0018", "PKGM0019"];

export function isMpkg(data) {
  const head = data.subarray(0, 64);
  const s = new TextDecoder("utf-8", { fatal: false }).decode(head);
  return MAGICS.some((m) => s.includes(m)) || s.startsWith("PKGM");
}

function findFtyp(data, from = 0) {
  const needle = [0x66, 0x74, 0x79, 0x70];
  for (let i = from; i <= data.length - 4; i++) {
    if (data[i] === needle[0] && data[i + 1] === needle[1] && data[i + 2] === needle[2] && data[i + 3] === needle[3]) return i;
  }
  return -1;
}

function u32be(data, i) {
  return ((data[i] << 24) | (data[i + 1] << 16) | (data[i + 2] << 8) | data[i + 3]) >>> 0;
}

function extractMp4Blobs(data) {
  const out = [];
  let idx = 0;
  while (true) {
    const i = findFtyp(data, idx);
    if (i < 0) break;
    if (i >= 4) {
      const size = u32be(data, i - 4);
      const start = i - 4;
      if (size >= 8 && start + size <= data.length) {
        out.push(data.slice(start, start + size));
      } else if (start >= 0) {
        out.push(data.slice(start, Math.min(data.length, i + 4096)));
      }
    }
    idx = i + 4;
  }
  // dedup by containment
  out.sort((a, b) => b.length - a.length);
  const kept = [];
  for (const b of out) {
    if (kept.some((k) => includesBytes(k, b))) continue;
    kept.push(b);
  }
  return kept;
}

function includesBytes(hay, needle) {
  if (needle.length > hay.length) return false;
  outer: for (let i = 0; i <= hay.length - needle.length; i += Math.max(1, needle.length >> 8)) {
    for (let j = 0; j < needle.length; j++) if (hay[i + j] !== needle[j]) continue outer;
    return true;
  }
  return false;
}

function carveMedia(data) {
  const results = [];
  for (const blob of extractMp4Blobs(data)) results.push({ ext: ".mp4", blob });
  const img = extractEmbedded(data);
  if (img.ext && img.ext !== ".mp4" && img.payload) results.push({ ext: img.ext, blob: img.payload });
  // standalone PNG
  const sig = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  let idx = 0;
  while (true) {
    let i = -1;
    for (let p = idx; p <= data.length - 8; p++) {
      if (sig.every((b, k) => data[p + k] === b)) { i = p; break; }
    }
    if (i < 0) break;
    let iend = -1;
    for (let p = i; p <= data.length - 4; p++) {
      if (data[p] === 0x49 && data[p + 1] === 0x45 && data[p + 2] === 0x4e && data[p + 3] === 0x44) { iend = p; break; }
    }
    const end = iend !== -1 ? iend + 8 : Math.min(data.length, i + 64 * 1024);
    if (end <= data.length) results.push({ ext: ".png", blob: data.slice(i, end) });
    idx = i + 1;
    if (results.length > 64) break;
  }
  return results;
}

export function extractMpkg(data) {
  if (data.length < 16) throw new AppError(label, "MPKG 文件过小");
  try {
    const { entries } = readPkgIndex(data);
    if (entries && entries.length < 500_000) {
      try {
        const { files } = extractPkg(data);
        const out = files.map((f) =>
          f.name.toLowerCase().endsWith(".tex")
            ? extractTex(f.blob, f.name.replace(/\.tex$/i, ""))
            : f
        );
        if (out.length) return { files: out };
      } catch {
        /* fall through */
      }
    }
  } catch {
    /* fall through */
  }
  const carved = carveMedia(data);
  if (!carved.length) {
    throw new AppError(label, "无法从 MPKG 中提取内容：未知加密或版本，请确认是 Wallpaper Engine 导出的 .mpkg");
  }
  return {
    files: carved.map((c, i) => ({
      name: `extracted_${String(i + 1).padStart(2, "0")}${c.ext}`,
      blob: c.blob,
    })),
  };
}
