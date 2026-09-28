let _idCounter = 0;
function _genId(prefix) {
  return `${prefix}_${++_idCounter}_${Date.now().toString(36)}`;
}

export function createDefaultParams() {
  return {
    transform: {
      rotation: 0,
      flipH: false,
      flipV: false,
      scale: 1.0,
      crop: null,
    },
    audio: {
      volume: 1.0,
      fadeIn: 0,
      fadeOut: 0,
      detune: 0,
    },
    overlay: null,
    filters: {
      brightness: 0,
      contrast: 0,
      saturation: 0,
      hue: 0,
      grayscale: false,
      sepia: false,
      blur: 0,
      sharpen: 0,
    },
  };
}

export class Clip {
  constructor({ id, sourceFile, timelineIn, sourceIn, sourceOut, speed, params }) {
    this.id = id || _genId("clip");
    this.sourceFile = sourceFile;
    this.timelineIn = timelineIn;
    this.sourceIn = sourceIn;
    this.sourceOut = sourceOut;
    this.speed = speed ?? 1.0;
    this.params = params || createDefaultParams();
  }

  get duration() {
    return (this.sourceOut - this.sourceIn) / this.speed;
  }

  splitAt(time) {
    const splitSource = this.sourceIn + time * this.speed;
    const c1 = new Clip({
      id: this.id,
      sourceFile: this.sourceFile,
      timelineIn: this.timelineIn,
      sourceIn: this.sourceIn,
      sourceOut: splitSource,
      speed: this.speed,
      params: JSON.parse(JSON.stringify(this.params)),
    });
    const c2 = new Clip({
      id: _genId("clip"),
      sourceFile: this.sourceFile,
      timelineIn: this.timelineIn + c1.duration,
      sourceIn: splitSource,
      sourceOut: this.sourceOut,
      speed: this.speed,
      params: JSON.parse(JSON.stringify(this.params)),
    });
    return [c1, c2];
  }

  clone() {
    return new Clip({
      id: _genId("clip"),
      sourceFile: this.sourceFile,
      timelineIn: this.timelineIn,
      sourceIn: this.sourceIn,
      sourceOut: this.sourceOut,
      speed: this.speed,
      params: JSON.parse(JSON.stringify(this.params)),
    });
  }

  toJSON() {
    return {
      id: this.id,
      sourceFile: this.sourceFile,
      timelineIn: this.timelineIn,
      sourceIn: this.sourceIn,
      sourceOut: this.sourceOut,
      speed: this.speed,
      params: this.params,
    };
  }
}

export class Track {
  constructor({ id, type, name, clips, muted, locked, visible }) {
    this.id = id || _genId("track");
    this.type = type;
    this.name = name || "";
    this.clips = clips || [];
    this.muted = muted ?? false;
    this.locked = locked ?? false;
    this.visible = visible ?? true;
  }

  addClip(clip) {
    this.clips.push(clip);
    this.clips.sort((a, b) => a.timelineIn - b.timelineIn);
  }

  removeClip(clipId) {
    this.clips = this.clips.filter((c) => c.id !== clipId);
  }

  replaceClip(oldId, newClips) {
    const idx = this.clips.findIndex((c) => c.id === oldId);
    if (idx === -1) return;
    this.clips.splice(idx, 1, ...newClips);
    this.clips.sort((a, b) => a.timelineIn - b.timelineIn);
  }

  toJSON() {
    return {
      id: this.id,
      type: this.type,
      name: this.name,
      clips: this.clips.map((c) => c.toJSON()),
      muted: this.muted,
      locked: this.locked,
      visible: this.visible,
    };
  }
}

export class TimelineModel {
  constructor({ id, name, tracks }) {
    this.id = id || _genId("timeline");
    this.name = name || "未命名";
    this.tracks = tracks || [];
  }

  get duration() {
    let max = 0;
    for (const track of this.tracks) {
      for (const clip of track.clips) {
        const end = clip.timelineIn + clip.duration;
        if (end > max) max = end;
      }
    }
    return max;
  }

  addTrack(track) {
    this.tracks.push(track);
  }

  removeTrack(trackId) {
    this.tracks = this.tracks.filter((t) => t.id !== trackId);
  }

  findClip(clipId) {
    for (const track of this.tracks) {
      for (const clip of track.clips) {
        if (clip.id === clipId) return clip;
      }
    }
    return null;
  }

  getClipTrack(clipId) {
    for (const track of this.tracks) {
      if (track.clips.some((c) => c.id === clipId)) return track;
    }
    return null;
  }

  toJSON() {
    return {
      version: 1,
      id: this.id,
      name: this.name,
      tracks: this.tracks.map((t) => t.toJSON()),
    };
  }

  static fromJSON(data) {
    const tracks = data.tracks.map((tdata) => {
      const track = new Track({
        id: tdata.id,
        type: tdata.type,
        name: tdata.name,
        muted: tdata.muted,
        locked: tdata.locked,
        visible: tdata.visible,
      });
      for (const cdata of tdata.clips) {
        track.clips.push(new Clip({
          id: cdata.id,
          sourceFile: cdata.sourceFile,
          timelineIn: cdata.timelineIn,
          sourceIn: cdata.sourceIn,
          sourceOut: cdata.sourceOut,
          speed: cdata.speed,
          params: cdata.params,
        }));
      }
      track.clips.sort((a, b) => a.timelineIn - b.timelineIn);
      return track;
    });
    return new TimelineModel({ id: data.id, name: data.name, tracks });
  }
}
