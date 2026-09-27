import { AppError } from "./errors.js";

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

/** File System Access API 在 Chromium 系浏览器可用；其他浏览器回退到打包下载。 */
export function supportsFileSystemAccess() {
  return typeof window !== "undefined" && typeof window.showDirectoryPicker === "function";
}

export async function pickOutputDirectory() {
  if (!supportsFileSystemAccess()) {
    throw new AppError("保存失败", "当前浏览器不支持直接保存到文件夹，请使用打包下载");
  }
  try {
    return await window.showDirectoryPicker({ mode: "readwrite" });
  } catch (e) {
    if (e && e.name === "AbortError") throw new AppError("保存失败", "已取消选择");
    throw new AppError("保存失败", `无法打开文件夹选择器: ${e && e.message ? e.message : e}`);
  }
}

export async function writeBlobToDirectory(dirHandle, blob, filename) {
  const fileHandle = await dirHandle.getFileHandle(filename, { create: true });
  const writable = await fileHandle.createWritable();
  try {
    await writable.write(blob);
  } finally {
    await writable.close();
  }
  return filename;
}

/** 顺序写入，避免大批量文件同时压盘。返回已写入的文件名。 */
export async function saveBlobsToDirectory(dirHandle, blobs) {
  const written = [];
  for (const { blob, filename } of blobs) {
    written.push(await writeBlobToDirectory(dirHandle, blob, filename));
  }
  return written;
}

/** 让元素可拖拽保存：把 Blob 包成 File 放进 DataTransfer，用户可拖到桌面/资源管理器。 */
export function enableDragSave(element, blob, filename) {
  if (!element || typeof element.setAttribute !== "function") return false;
  element.setAttribute("draggable", "true");
  element.addEventListener("dragstart", (ev) => {
    const dt = ev.dataTransfer;
    if (!dt || typeof dt.items !== "object" || !dt.items.add) return;
    dt.items.add(new File([blob], filename, { type: blob.type || "application/octet-stream" }));
    dt.effectAllowed = "copy";
  });
  return true;
}

export function baseName(pathLike) {
  const s = String(pathLike).replace(/\\/g, "/");
  const i = s.lastIndexOf("/");
  return i >= 0 ? s.slice(i + 1) : s;
}

export function stem(name) {
  const b = baseName(name);
  const i = b.lastIndexOf(".");
  return i > 0 ? b.slice(0, i) : b;
}
