import { needsProcessing } from "./filters.js";

export class ExportOrchestrator {
  constructor(timeline, options, adapter) {
    this.timeline = timeline;
    this.options = options;
    this.adapter = adapter;
    this.cancelled = false;
  }

  async export(onProgress) {
    const plan = this._buildPlan();
    const intermediates = [];

    try {
      for (let i = 0; i < plan.clips.length; i++) {
        if (this.cancelled) throw new Error("已取消");
        const clip = plan.clips[i];
        onProgress(Math.round(((i / plan.clips.length) * 50)), `预处理片段 ${i + 1}/${plan.clips.length}`);

        if (clip.needsProcessing) {
          const outName = `prep_${i}.mp4`;
          await this._processClip(clip, outName, (p) => {
            onProgress(Math.round(((i + p / 100) / plan.clips.length) * 50), `预处理片段 ${i + 1}/${plan.clips.length}`);
          });
          intermediates.push(outName);
          clip.processedFile = outName;
        }
      }

      if (this.cancelled) throw new Error("已取消");
      onProgress(50, "合成最终视频…");
      const outputName = `output.${this.options.format || "mp4"}`;
      await this._compose(plan, outputName, intermediates, (p) => {
        onProgress(Math.round(50 + p / 2), "合成最终视频…");
      });
      if (this.cancelled) throw new Error("已取消");
      intermediates.push(outputName);

      onProgress(100, "导出完成");
      const blob = await this.adapter.readFile(outputName);
      return { blob, filename: outputName };
    } finally {
      for (const name of intermediates) {
        try { await this.adapter.deleteFile(name); } catch { /* ignore */ }
      }
    }
  }

  _buildPlan() {
    const clips = [];
    for (const track of this.timeline.tracks) {
      if (track.type !== "video" || track.muted) continue;
      for (const clip of track.clips) {
        clips.push({
          ...clip,
          needsProcessing: needsProcessing(clip),
          processedFile: null,
        });
      }
    }
    clips.sort((a, b) => a.timelineIn - b.timelineIn);
    return { clips };
  }

  async _processClip(clip, outName, onProgress) {
    const args = ["-i", clip.sourceFile];
    args.push("-ss", String(clip.sourceIn), "-t", String(clip.sourceOut - clip.sourceIn));

    const { buildClipFilter } = await import("./filters.js");
    const filter = buildClipFilter(clip, 0, 0);
    if (filter) args.push("-vf", filter);

    if (clip.params.audio.volume !== 1.0) {
      args.push("-af", `volume=${clip.params.audio.volume}`);
    }

    args.push("-c:v", this.options.videoCodec || "libx264", "-preset", this.options.preset || "veryfast", "-crf", String(this.options.crf ?? 23));
    args.push("-pix_fmt", "yuv420p");
    args.push("-c:a", this.options.audioCodec || "aac", "-ar", "48000", "-ac", "2");
    args.push(outName);

    await this.adapter.runFFmpeg(args, outName, (p) => onProgress(p));
  }

  async _compose(plan, outName, intermediates, onProgress) {
    const videoClips = plan.clips;

    if (videoClips.length === 1) {
      const clip = videoClips[0];
      const src = clip.processedFile || clip.sourceFile;
      await this.adapter.runFFmpeg(["-i", src, "-c", "copy", outName], outName, (p) => onProgress(p));
      return;
    }

    const concatList = videoClips.map((c) => `file '${c.processedFile || c.sourceFile}'`).join("\n");
    await this.adapter.writeFile("concat.txt", concatList);
    intermediates.push("concat.txt");

    const args = ["-f", "concat", "-safe", "0", "-i", "concat.txt"];
    args.push("-c:v", this.options.videoCodec || "libx264", "-preset", this.options.preset || "veryfast", "-crf", String(this.options.crf ?? 23));
    args.push("-pix_fmt", "yuv420p");
    args.push("-c:a", this.options.audioCodec || "aac", "-ar", "48000", "-ac", "2");
    args.push(outName);

    await this.adapter.runFFmpeg(args, outName, (p) => onProgress(p));
  }
}
