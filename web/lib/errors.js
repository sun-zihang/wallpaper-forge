export class AppError extends Error {
  constructor(label, detail = "") {
    super(detail || label);
    this.label = label;
    this.detail = detail;
  }
}

export function friendlyError(e) {
  if (e instanceof AppError) {
    return e.detail ? `${e.label}：${e.detail}` : e.label;
  }
  if (e && typeof e === "object" && e.name === "AbortError") {
    return "已取消";
  }
  const msg = String((e && e.message) || e);
  if (msg.includes("已取消")) return "已取消";
  return `未知错误：${msg}`;
}
