import { AppError } from "./errors.js";

const label = "PKG 解包失败";

function readU32(data, pos) {
  if (pos + 4 > data.length) throw new AppError(label, "PKG 文件损坏：读取长度字段失败");
  return [(data[pos] | (data[pos + 1] << 8) | (data[pos + 2] << 16) | (data[pos + 3] << 24)) >>> 0, pos + 4];
}

export function readPkgIndex(data) {
  if (data.length < 8) throw new AppError(label, "PKG 文件过小");
  let [headerLen, pos] = readU32(data, 0);
  if (headerLen > data.length - 4) throw new AppError(label, "不是有效的 Wallpaper Engine 包（头部长度异常）");
  const headerBytes = data.subarray(pos, pos + headerLen);
  pos += headerLen;
  const magic = new TextDecoder("utf-8", { fatal: false }).decode(headerBytes).replace(/\0+$/, "");
  if (headerLen && !/^(PKG|PKGM)/i.test(magic) && headerLen > 1024) {
    throw new AppError(label, `不是有效的 Wallpaper Engine 包（头部: ${magic.slice(0, 40)}）`);
  }
  let [count, pos2] = readU32(data, pos);
  pos = pos2;
  if (count > 1_000_000) throw new AppError(label, "不是有效的 Wallpaper Engine 包（文件数异常）");
  const entries = [];
  const td = new TextDecoder("utf-8", { fatal: false });
  for (let i = 0; i < count; i++) {
    let nameLen;
    [nameLen, pos] = readU32(data, pos);
    if (nameLen > 4096 || pos + nameLen + 8 > data.length) throw new AppError(label, "PKG 索引损坏");
    let name = td.decode(data.subarray(pos, pos + nameLen)).replace(/\0+$/, "").replace(/\\/g, "/");
    pos += nameLen;
    let offset, length;
    [offset, pos] = readU32(data, pos);
    [length, pos] = readU32(data, pos);
    entries.push({ name, offset, length });
  }
  return { magic, entries, indexEnd: pos };
}

function indexEnd(data) {
  let [headerLen, pos] = readU32(data, 0);
  pos += headerLen;
  let count;
  [count, pos] = readU32(data, pos);
  for (let i = 0; i < count; i++) {
    let nameLen;
    [nameLen, pos] = readU32(data, pos);
    pos += nameLen + 8;
  }
  return pos;
}

export function extractPkg(data) {
  const { entries } = readPkgIndex(data);
  const dataStart = indexEnd(data);
  const files = [];
  for (const entry of entries) {
    let start = dataStart + entry.offset;
    let end = start + entry.length;
    if (entry.length < 0 || start < 0 || end > data.length) {
      start = entry.offset;
      end = entry.offset + entry.length;
      if (end > data.length || start < 0) throw new AppError(label, `条目越界: ${entry.name}`);
    }
    const name = entry.name.replace(/^\/+/, "");
    if (name.split("/").some((seg) => seg === "..")) {
      throw new AppError(label, `非法路径: ${entry.name}`);
    }
    files.push({ name, blob: data.slice(start, end) });
  }
  return { files };
}
