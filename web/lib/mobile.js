// Mobile policy helpers. Mobile WASM throughput is 30–50% lower than desktop,
// so the video page silently clamps transcode parameters to 1080P-class and
// tells the user once. Detection is heuristic by design (UA hint -> viewport
// width -> UA string); a desktop-window tablet simply gets desktop behavior.
export const MOBILE_MAX_VIDEO_WIDTH = 1920;
export const MOBILE_VIDEO_NOTE = "移动端硬件受限，已自动优化处理参数以保证流畅度。";

export function isMobileDevice({ userAgent = "", mobile = false, screenWidth = Infinity } = {}) {
  if (mobile === true) return true;
  if (Number.isFinite(screenWidth) && screenWidth > 0 && screenWidth < 768) return true;
  return /Android|iPhone|iPad|iPod|Mobile|HarmonyOS/i.test(String(userAgent));
}

export function detectMobile(nav = globalThis.navigator) {
  if (!nav) return false;
  const ud = nav.userAgentData;
  return isMobileDevice({
    userAgent: nav.userAgent || "",
    mobile: ud ? Boolean(ud.mobile) : false,
    screenWidth: globalThis.innerWidth || 0,
  });
}

// Output-side scale cap: never upscale (`min(N,iw)`), keep even dimensions for
// yuv420p (`-2`).
export function mobileScaleArgs(maxWidth = MOBILE_MAX_VIDEO_WIDTH) {
  return ["-vf", `scale='min(${maxWidth},iw)':-2`];
}
