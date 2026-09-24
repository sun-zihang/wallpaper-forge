export function validateSelection(files, { extensions = null, maxSize = 0 } = {}) {
  const errors = [];
  const list = [...(files || [])];
  const kept = [];
  for (const f of list) {
    const name = (f && f.name) || "";
    if (f && f.size === 0) {
      errors.push({ name, reason: "文件为空" });
      continue;
    }
    if (maxSize && f && f.size > maxSize) {
      errors.push({ name, reason: `超过上限 ${Math.round(maxSize / 1024 / 1024)}MB` });
      continue;
    }
    if (extensions && extensions.length) {
      const lower = name.toLowerCase();
      if (!extensions.some((e) => lower.endsWith(String(e).toLowerCase()))) {
        errors.push({ name, reason: `不支持的文件类型（仅支持 ${extensions.join("、")}）` });
        continue;
      }
    }
    kept.push(f);
  }
  return { ok: errors.length === 0, errors, files: kept };
}
