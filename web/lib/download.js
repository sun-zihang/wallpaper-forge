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
