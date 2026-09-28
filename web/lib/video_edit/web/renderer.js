export class WebPreviewRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.videoElements = new Map();
    this.maxCachedVideos = 5;
    this.accessOrder = [];
  }

  async render(frameDesc) {
    const { videoLayers, overlays, time } = frameDesc;
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    for (const layer of videoLayers) {
      await this._renderVideoLayer(layer);
    }

    for (const ov of overlays) {
      await this._renderOverlay(ov);
    }
  }

  async _renderVideoLayer(layer) {
    const { clip, sourceTime, params } = layer;
    const video = this._getVideoElement(clip);
    if (Math.abs(video.currentTime - sourceTime) > 0.1) {
      video.currentTime = sourceTime;
      await this._seeked(video);
    }

    this.ctx.save();
    const w = this.canvas.width;
    const h = this.canvas.height;

    if (params.transform.crop) {
      const { x, y, width, height } = params.transform.crop;
      this.ctx.drawImage(video, x, y, width, height, 0, 0, w, h);
    } else {
      this.ctx.drawImage(video, 0, 0, w, h);
    }

    this.ctx.restore();
  }

  async _renderOverlay(ov) {
    const overlay = ov.clip.params.overlay;
    if (!overlay) return;

    if (overlay.type === "text") {
      this.ctx.save();
      const x = this.canvas.width * (overlay.position.x / 100);
      const y = this.canvas.height * (overlay.position.y / 100);
      this.ctx.font = `${overlay.fontSize}px sans-serif`;
      this.ctx.fillStyle = overlay.fontColor;
      this.ctx.globalAlpha = overlay.opacity;
      this.ctx.fillText(overlay.text, x, y);
      this.ctx.restore();
    } else if (overlay.type === "image") {
      const img = await this._loadImage(overlay.imageFile);
      if (img) {
        this.ctx.save();
        const x = this.canvas.width * (overlay.position.x / 100);
        const y = this.canvas.height * (overlay.position.y / 100);
        this.ctx.globalAlpha = overlay.opacity;
        this.ctx.drawImage(img, x, y, img.width * overlay.scale, img.height * overlay.scale);
        this.ctx.restore();
      }
    }
  }

  _getVideoElement(clip) {
    if (!this.videoElements.has(clip.id)) {
      if (this.videoElements.size >= this.maxCachedVideos) {
        const oldest = this.accessOrder.shift();
        if (oldest) {
          const v = this.videoElements.get(oldest);
          if (v) { v.src = ""; }
          this.videoElements.delete(oldest);
        }
      }
      const v = document.createElement("video");
      v.src = URL.createObjectURL(clip.sourceFile);
      v.muted = true;
      v.preload = "auto";
      this.videoElements.set(clip.id, v);
    }
    this._touch(clip.id);
    return this.videoElements.get(clip.id);
  }

  _touch(clipId) {
    const idx = this.accessOrder.indexOf(clipId);
    if (idx !== -1) this.accessOrder.splice(idx, 1);
    this.accessOrder.push(clipId);
  }

  _seeked(video) {
    return new Promise((resolve) => {
      const handler = () => {
        video.removeEventListener("seeked", handler);
        resolve();
      };
      video.addEventListener("seeked", handler);
      setTimeout(resolve, 200);
    });
  }

  _loadImage(src) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      img.src = src;
    });
  }

  setQuality(quality) {
    this.canvas.width = 1280 * quality;
    this.canvas.height = 720 * quality;
  }
}
