// web/lib/onboarding.js
// 首次访问的分步引导。完成后写入 localStorage，不再打扰。
const STORE_KEY = "wc.onboarded";

const STEPS = [
  { title: "功能分区", body: "左侧导航支持图片、GIF、视频转换和项目解包，文件全部在本机浏览器处理。" },
  { title: "添加文件", body: "把文件拖到虚线区域，或点击选择文件。所有处理都在本地完成，不会上传到任何服务器。" },
  { title: "调整参数", body: "在参数面板调整输出格式、质量、尺寸等，作业表会实时显示每个文件的进度。" },
  { title: "处理与下载", body: "处理完成后，打包下载 ZIP 或保存到本地文件夹；也可以按 ? 查看键盘快捷键。" },
];

let overlay = null;
let step = 0;

function finish() {
  try {
    localStorage.setItem(STORE_KEY, "1");
  } catch { /* ignore */ }
  if (overlay) {
    overlay.remove();
    overlay = null;
  }
}

function render() {
  if (!overlay) return;
  const s = STEPS[step];
  const last = step === STEPS.length - 1;
  overlay.innerHTML = `
    <div class="onboarding-card">
      <div class="onboarding-step">第 ${step + 1} / ${STEPS.length} 步</div>
      <h2>${s.title}</h2>
      <p>${s.body}</p>
      <div class="onboarding-actions">
        <button type="button" class="btn secondary" data-act="skip">跳过引导</button>
        <button type="button" class="btn" data-act="next">${last ? "完成" : "下一步"}</button>
      </div>
    </div>
  `;
  overlay.querySelector('[data-act="skip"]').addEventListener("click", finish);
  overlay.querySelector('[data-act="next"]').addEventListener("click", () => {
    if (last) finish();
    else {
      step += 1;
      render();
    }
  });
}

export function maybeShowOnboarding() {
  try {
    if (localStorage.getItem(STORE_KEY)) return;
  } catch { /* ignore */ }
  if (typeof document === "undefined" || !document.body) return;
  overlay = document.createElement("div");
  overlay.className = "onboarding";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-label", "新手引导");
  document.body.appendChild(overlay);
  step = 0;
  render();
}
