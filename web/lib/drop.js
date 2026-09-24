export function filterDropped(files, extensions = null) {
  const list = [...(files || [])];
  if (!extensions || !extensions.length) return { kept: list, rejected: [] };
  const kept = [];
  const rejected = [];
  for (const f of list) {
    const name = ((f && f.name) || "").toLowerCase();
    if (extensions.some((e) => name.endsWith(String(e).toLowerCase()))) kept.push(f);
    else rejected.push(f);
  }
  return { kept, rejected };
}

export function attachDropTarget(el, input, { extensions = null, onRejected } = {}) {
  if (!el || !input) return;
  el.addEventListener("dragover", (ev) => {
    ev.preventDefault();
  });
  el.addEventListener("drop", async (ev) => {
    ev.preventDefault();
    const dropped = [...(ev.dataTransfer?.files || [])];
    if (!dropped.length) return;
    const { kept, rejected } = filterDropped(dropped, extensions);
    if (onRejected && rejected.length) {
      const names = rejected.map((f) => f.name).join("、");
      onRejected(`已忽略不支持的文件：${names}`);
    }
    if (!kept.length) return;
    const existing = [...input.files];
    const merged = [...existing, ...kept];
    const dt = new DataTransfer();
    for (const f of merged) dt.items.add(f);
    input.files = dt.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
}
