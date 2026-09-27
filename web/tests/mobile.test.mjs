import test from "node:test";
import assert from "node:assert/strict";
import {
  isMobileDevice,
  detectMobile,
  mobileScaleArgs,
  MOBILE_MAX_VIDEO_WIDTH,
  MOBILE_VIDEO_NOTE,
} from "../lib/mobile.js";

test("userAgentData mobile hint wins", () => {
  assert.ok(isMobileDevice({ userAgent: "Mozilla/5.0", mobile: true, screenWidth: 2560 }));
});

test("narrow viewport counts as mobile", () => {
  assert.ok(isMobileDevice({ userAgent: "Mozilla/5.0", screenWidth: 480 }));
  assert.ok(!isMobileDevice({ userAgent: "Mozilla/5.0", screenWidth: 768 }));
});

test("desktop UA on a wide screen is not mobile", () => {
  assert.ok(
    !isMobileDevice({
      userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      screenWidth: 1920,
    }),
  );
});

test("mobile UA strings are recognized on wide screens too", () => {
  for (const ua of [
    "Mozilla/5.0 (Linux; Android 14; Pixel 8)",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)",
    "Mozilla/5.0 (Linux; HarmonyOS)",
  ]) {
    assert.ok(isMobileDevice({ userAgent: ua, screenWidth: 1920 }), ua);
  }
});

test("zero/unknown screen width falls through to the UA check", () => {
  assert.ok(!isMobileDevice({ userAgent: "Mozilla/5.0", screenWidth: 0 }));
  assert.ok(isMobileDevice({ userAgent: "Android", screenWidth: 0 }));
});

test("detectMobile reads navigator-like input and defaults to false in tests", () => {
  assert.ok(
    detectMobile({
      userAgent: "Mozilla/5.0 (Linux; Android 14)",
      userAgentData: { mobile: true },
    }),
  );
  assert.ok(!detectMobile({ userAgent: "Mozilla/5.0 (Macintosh)", userAgentData: { mobile: false } }));
  assert.ok(!detectMobile(null));
});

test("mobileScaleArgs builds a capped, even-height, never-upscaling filter", () => {
  assert.deepEqual(mobileScaleArgs(), ["-vf", `scale='min(${MOBILE_MAX_VIDEO_WIDTH},iw)':-2`]);
  assert.deepEqual(mobileScaleArgs(1080), ["-vf", "scale='min(1080,iw)':-2"]);
});

test("policy constants stay aligned", () => {
  assert.equal(MOBILE_MAX_VIDEO_WIDTH, 1920);
  assert.ok(MOBILE_VIDEO_NOTE.includes("移动端"));
});
