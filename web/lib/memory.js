// web/lib/memory.js
// 长时间批量任务期间的内存监控。performance.memory 仅 Chromium 系提供，
// 其他浏览器下监控器退化为无操作，不影响功能。
export function createMemoryMonitor({ intervalMs = 5000, limitMb = 1500, onWarning } = {}) {
  const mem = typeof performance !== "undefined" ? performance.memory : null;
  if (!mem || typeof mem.usedJSHeapSize !== "number") {
    return {
      stop() {},
      get usageMb() {
        return null;
      },
    };
  }
  const timer = setInterval(() => {
    const used = mem.usedJSHeapSize / (1024 * 1024);
    if (used > limitMb && typeof onWarning === "function") onWarning(used);
  }, intervalMs);
  return {
    stop() {
      clearInterval(timer);
    },
    get usageMb() {
      return mem.usedJSHeapSize / (1024 * 1024);
    },
  };
}
