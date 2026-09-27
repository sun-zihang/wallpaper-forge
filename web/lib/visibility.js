// web/lib/visibility.js
// 标签页可见性追踪。切到后台时浏览器会节流定时器与 rAF，
// 但 ffmpeg.wasm 跑在独立 Worker 内、图片处理是异步 Canvas 操作，
// 都不受影响；这里负责给用户明确的状态提示。
export function isDocumentHidden() {
  return typeof document !== "undefined" && document.hidden === true;
}

export function onVisibilityChange(cb) {
  if (typeof document === "undefined" || typeof document.addEventListener !== "function") {
    return () => {};
  }
  const handler = () => cb(document.hidden === true);
  document.addEventListener("visibilitychange", handler);
  return () => document.removeEventListener("visibilitychange", handler);
}
