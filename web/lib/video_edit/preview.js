export class PreviewCalculator {
  getFrameAt(timeline, t) {
    const layers = [];
    for (const track of timeline.tracks) {
      if (track.muted) continue;
      for (const clip of track.clips) {
        if (t >= clip.timelineIn && t < clip.timelineIn + clip.duration) {
          layers.push({ clip, sourceTime: this._computeSourceTime(clip, t), params: clip.params, trackType: track.type });
        }
      }
    }
    return {
      videoLayers: layers.filter((l) => l.trackType === "video"),
      audioLayers: layers.filter((l) => l.trackType === "audio"),
      overlays: layers.filter((l) => l.trackType === "overlay"),
      time: t,
    };
  }

  getAudioMixAt(timeline, t) {
    const result = [];
    for (const track of timeline.tracks) {
      if (track.type !== "audio" || track.muted) continue;
      for (const clip of track.clips) {
        if (t >= clip.timelineIn && t < clip.timelineIn + clip.duration) {
          result.push({
            clip,
            sourceTime: this._computeSourceTime(clip, t),
            effectiveVolume: this._computeEffectiveVolume(clip, t),
          });
        }
      }
    }
    return result;
  }

  _computeSourceTime(clip, t) {
    return clip.sourceIn + (t - clip.timelineIn) * clip.speed;
  }

  _computeEffectiveVolume(clip, t) {
    const localT = t - clip.timelineIn;
    let vol = clip.params.audio.volume;
    const { fadeIn, fadeOut } = clip.params.audio;
    if (fadeIn > 0 && localT < fadeIn) {
      vol *= localT / fadeIn;
    }
    if (fadeOut > 0) {
      const remaining = clip.duration - localT;
      if (remaining < fadeOut) {
        vol *= Math.max(0, remaining) / fadeOut;
      }
    }
    return Math.max(0, vol);
  }
}
