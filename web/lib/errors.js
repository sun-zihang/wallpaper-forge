export class AppError extends Error {
  constructor(label, detail = "") {
    super(detail || label);
    this.label = label;
    this.detail = detail;
  }
}

/**
 * 把错误归成几类，每类配一句人话和一个可操作建议。
 * 用户看到的是「发生了什么 + 怎么办」，而不是堆栈。
 */
export function classifyError(e) {
  const msg = String((e && e.message) || e);
  const name = (e && e.name) || "";
  if (name === "AbortError" || msg.includes("已取消")) {
    return { category: "cancelled", message: "已取消", advice: "" };
  }
  if (
    msg.includes("文件头无法识别") ||
    msg.includes("无法读取图片") ||
    msg.includes("无法读取 GIF") ||
    msg.includes("无法读取视频") ||
    msg.includes("没有可导出的帧") ||
    msg.includes("gifuct 加载失败") ||
    msg.includes("JSZip 加载失败")
  ) {
    return {
      category: "corrupt",
      message: "文件损坏或格式无法识别",
      advice: "文件可能已损坏，或使用了不支持的编码。试试重新下载/导出，或换用桌面版。",
    };
  }
  if ((msg.includes("超过") && msg.includes("上限")) || msg.includes("分辨率过高") || msg.includes("尺寸异常")) {
    return {
      category: "limit",
      message: "超出 Web 端处理上限",
      advice: "Web 端有大小/时长/分辨率限制，超出请使用桌面版（无此限制）。",
    };
  }
  if (msg.includes("引擎加载失败") || msg.includes("FFmpeg") || msg.includes("无法加载依赖")) {
    return {
      category: "engine",
      message: "处理引擎加载失败",
      advice: "请检查网络连接，使用最新版 Chrome / Edge，或清除浏览器缓存后重试。",
    };
  }
  if (msg.includes("内存")) {
    return { category: "memory", message: "内存不足", advice: "减少同时处理的文件数量，或降低输出分辨率。" };
  }
  return { category: "unknown", message: "处理失败", advice: msg };
}

export function friendlyError(e) {
  if (e instanceof AppError) {
    const c = classifyError(e);
    if (c.category === "unknown") {
      return e.detail ? `${e.label}：${e.detail}` : e.label;
    }
    if (c.category === "limit" && e.detail) {
      return `${c.message}：${e.detail}`;
    }
    return c.advice ? `${c.message}：${c.advice}` : c.message;
  }
  if (e && e.name === "AbortError") return "已取消";
  const msg = String((e && e.message) || e);
  if (msg.includes("已取消")) return "已取消";
  const c = classifyError(e);
  if (c.category === "unknown") return `未知错误：${msg}`;
  return c.advice ? `${c.message}：${c.advice}` : c.message;
}
