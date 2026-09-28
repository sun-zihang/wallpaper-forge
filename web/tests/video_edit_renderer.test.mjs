// web/tests/video_edit_renderer.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { WebPreviewRenderer } from "../lib/video_edit/web/renderer.js";

function installDom() {
  const ctxCalls = [];
  const ctx = {
    font: "",
    fillStyle: "",
    globalAlpha: 1,
    clearRect(...a) {
      ctxCalls.push(["clearRect", a]);
    },
    save() {},
    restore() {},
    drawImage(...a) {
      ctxCalls.push(["drawImage", a]);
    },
    fillText(...a) {
      ctxCalls.push(["fillText", a]);
    },
  };
  const videos = [];
  globalThis.document = {
    createElement(tag) {
      if (tag !== "video") throw new Error(`unexpected element ${tag}`);
      const v = {
        currentTime: 0,
        muted: false,
        preload: "",
        src: "",
        addEventListener(type, h) {
          if (type === "seeked") setTimeout(h, 0);
        },
        removeEventListener() {},
      };
      videos.push(v);
      return v;
    },
  };
  globalThis.Image = class FakeImage {
    set src(v) {
      this.width = 8;
      this.height = 8;
      setTimeout(() => {
        if (String(v).includes("bad")) this.onerror?.();
        else this.onload?.();
      }, 0);
    }
  };
  globalThis.URL = { createObjectURL: () => "blob:fake" };
  const canvas = { width: 640, height: 360, getContext: () => ctx };
  return { canvas, ctxCalls, videos };
}

const overlayClip = (overlay) => ({ clip: { params: overlay ? { overlay } : {} } });
const videoLayer = (clip, sourceTime, crop) => ({
  clip,
  sourceTime,
  params: { transform: { crop } },
});

test("render draws text overlays at percentage positions", async () => {
  const { canvas, ctxCalls } = installDom();
  const r = new WebPreviewRenderer(canvas);
  await r.render({
    videoLayers: [],
    overlays: [
      overlayClip({
        type: "text",
        text: "Hi",
        position: { x: 50, y: 50 },
        fontSize: 24,
        fontColor: "#fff",
        opacity: 0.5,
      }),
    ],
    time: 0,
  });
  const fills = ctxCalls.filter(([n]) => n === "fillText");
  assert.equal(fills.length, 1);
  assert.deepEqual(fills[0][1], ["Hi", 320, 180]);
});

test("render loads image overlays and skips broken ones", async () => {
  const { canvas, ctxCalls } = installDom();
  const r = new WebPreviewRenderer(canvas);
  await r.render({
    videoLayers: [],
    overlays: [
      overlayClip({
        type: "image",
        imageFile: "data:image/png;base64,ok",
        position: { x: 10, y: 20 },
        opacity: 0.8,
        scale: 2,
      }),
      overlayClip({
        type: "image",
        imageFile: "bad",
        position: { x: 10, y: 20 },
        opacity: 1,
        scale: 1,
      }),
      overlayClip(null),
      overlayClip({ type: "unknown" }),
    ],
    time: 0,
  });
  const imgs = ctxCalls.filter(([n]) => n === "drawImage");
  assert.equal(imgs.length, 1, "only the loaded image is drawn");
  assert.equal(imgs[0][1][3], 16, "drawn at scale * width");
});

test("render crops video layers, skips redundant seeks, and evicts LRU videos", async () => {
  const { canvas, ctxCalls, videos } = installDom();
  const r = new WebPreviewRenderer(canvas);
  const clip = (i) => ({ id: `c${i}`, sourceFile: { name: `${i}.mp4` } });

  await r.render({
    videoLayers: [videoLayer(clip(0), 1, { x: 0, y: 0, width: 100, height: 100 })],
    overlays: [],
    time: 0,
  });
  let draws = ctxCalls.filter(([n]) => n === "drawImage");
  assert.equal(draws.length, 1, "crop drawImage path taken");
  assert.equal(draws[0][1].length, 9, "9-arg crop call");

  await r.render({
    videoLayers: [videoLayer(clip(0), 1.05, null)],
    overlays: [],
    time: 0,
  });
  draws = ctxCalls.filter(([n]) => n === "drawImage");
  assert.equal(draws[draws.length - 1][1].length, 5, "plain 5-arg draw call");
  assert.equal(r.videoElements.size, 1, "video element cached and reused");

  for (let i = 1; i <= 5; i += 1) {
    await r.render({
      videoLayers: [videoLayer(clip(i), 0.5, null)],
      overlays: [],
      time: 0,
    });
  }
  assert.equal(r.videoElements.size, 5, "cache capped at maxCachedVideos");
  assert.equal(videos[0].src, "", "oldest video src released");
  assert.equal(r.videoElements.has("c0"), false, "oldest clip evicted");
});

test("setQuality resizes the backing canvas", () => {
  const { canvas } = installDom();
  const r = new WebPreviewRenderer(canvas);
  r.setQuality(0.5);
  assert.equal(canvas.width, 640);
  assert.equal(canvas.height, 360);
});
