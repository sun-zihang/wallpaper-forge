export class WebAdapter {
  constructor(ffmpeg) {
    this.ffmpeg = ffmpeg;
  }

  async runFFmpeg(args, outPath, onProgress) {
    const code = await this.ffmpeg.exec(args);
    if (code !== 0) {
      throw new Error(`FFmpeg 失败，返回码 ${code}`);
    }
    if (onProgress) onProgress(100);
  }

  async writeFile(name, content) {
    const blob = content instanceof Blob ? content : new Blob([content]);
    const buf = new Uint8Array(await blob.arrayBuffer());
    await this.ffmpeg.writeFile(name, buf);
  }

  async readFile(name) {
    const data = await this.ffmpeg.readFile(name);
    const bytes = data instanceof Uint8Array ? data : new Uint8Array(data);
    return new Blob([bytes]);
  }

  async deleteFile(name) {
    try { await this.ffmpeg.deleteFile(name); } catch { /* ignore */ }
  }
}
