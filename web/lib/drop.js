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

let activeTarget = null;

export function bindDocumentDrop() {
  document.addEventListener("dragover", (ev) => {
    if (activeTarget && ev.dataTransfer?.types?.includes("Files")) ev.preventDefault();
  });
  document.addEventListener("drop", (ev) => {
    if (!activeTarget) return;
    ev.preventDefault();
    const files = [...(ev.dataTransfer?.files || [])];
    if (files.length) activeTarget(files);
  });
}

export function attachDropTarget(el, input, { extensions = null, onRejected } = {}) {
  const apply = (dropped) => {
    const { kept, rejected } = filterDropped(dropped, extensions);
    if (onRejected && rejected.length) {
      const names = rejected.map((f) => f.name).join("、");
      onRejected(`已忽略不支持的文件：${names}`);
    }
    if (!kept.length || !input) return;
    const existing = [...input.files];
    const merged = [...existing, ...kept];
    const dt = new DataTransfer();
    for (const f of merged) dt.items.add(f);
    input.files = dt.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  };
  activeTarget = apply;
  if (!el) return;
  el.addEventListener("dragover", (ev) => {
    ev.preventDefault();
    el.classList.add("hot");
  });
  el.addEventListener("dragleave", () => el.classList.remove("hot"));
  el.addEventListener("drop", (ev) => {
    ev.preventDefault();
    el.classList.remove("hot");
    apply([...(ev.dataTransfer?.files || [])]);
  });
}
