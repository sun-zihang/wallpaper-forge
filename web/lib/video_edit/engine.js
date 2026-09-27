// web/lib/video_edit/engine.js
import { Clip, createDefaultParams } from "./model.js";

const MAX_UNDO = 50;

export class EditEngine {
  constructor(timeline) {
    this.timeline = timeline;
    this.undoStack = [];
    this.redoStack = [];
  }

  execute(command) {
    command.redo(this.timeline);
    this.undoStack.push(command);
    this.redoStack = [];
    if (this.undoStack.length > MAX_UNDO) this.undoStack.shift();
  }

  undo() {
    const cmd = this.undoStack.pop();
    if (!cmd) return false;
    cmd.undo(this.timeline);
    this.redoStack.push(cmd);
    return true;
  }

  redo() {
    const cmd = this.redoStack.pop();
    if (!cmd) return false;
    cmd.redo(this.timeline);
    this.undoStack.push(cmd);
    return true;
  }
}

export class SplitClipCommand {
  constructor(clipId, time) {
    this.clipId = clipId;
    this.time = time;
    this.newClipId = null;
    this.originalClip = null;
  }

  redo(tl) {
    const clip = tl.findClip(this.clipId);
    if (!clip) return;
    this.originalClip = clip;
    const [c1, c2] = clip.splitAt(this.time);
    this.newClipId = c2.id;
    tl.getClipTrack(this.clipId).replaceClip(this.clipId, [c1, c2]);
  }

  undo(tl) {
    const track = tl.getClipTrack(this.clipId);
    if (!track || !this.originalClip) return;
    track.replaceClip(this.clipId, [this.originalClip]);
    track.removeClip(this.newClipId);
  }
}

export class RemoveClipCommand {
  constructor(clipId) {
    this.clipId = clipId;
    this.removedClip = null;
    this.trackId = null;
    this.index = -1;
  }

  redo(tl) {
    const track = tl.getClipTrack(this.clipId);
    if (!track) return;
    this.removedClip = tl.findClip(this.clipId);
    this.trackId = track.id;
    this.index = track.clips.indexOf(this.removedClip);
    track.removeClip(this.clipId);
  }

  undo(tl) {
    const track = tl.tracks.find((t) => t.id === this.trackId);
    if (!track || !this.removedClip) return;
    track.clips.splice(Math.min(this.index, track.clips.length), 0, this.removedClip);
    track.clips.sort((a, b) => a.timelineIn - b.timelineIn);
  }
}

export class MoveClipCommand {
  constructor(clipId, newTrackId, newIn) {
    this.clipId = clipId;
    this.newTrackId = newTrackId;
    this.newIn = newIn;
    this.oldTrackId = null;
    this.oldIn = null;
  }

  redo(tl) {
    const clip = tl.findClip(this.clipId);
    if (!clip) return;
    const oldTrack = tl.getClipTrack(this.clipId);
    this.oldTrackId = oldTrack.id;
    this.oldIn = clip.timelineIn;
    oldTrack.removeClip(this.clipId);
    clip.timelineIn = this.newIn;
    const newTrack = tl.tracks.find((t) => t.id === this.newTrackId);
    if (newTrack) newTrack.addClip(clip);
  }

  undo(tl) {
    const clip = tl.findClip(this.clipId);
    if (!clip) return;
    const currentTrack = tl.getClipTrack(this.clipId);
    if (currentTrack) currentTrack.removeClip(this.clipId);
    clip.timelineIn = this.oldIn;
    const oldTrack = tl.tracks.find((t) => t.id === this.oldTrackId);
    if (oldTrack) oldTrack.addClip(clip);
  }
}

export class AdjustParamsCommand {
  constructor(clipId, partialParams) {
    this.clipId = clipId;
    this.partialParams = partialParams;
    this.oldParams = null;
    this.oldSpeed = null;
  }

  redo(tl) {
    const clip = tl.findClip(this.clipId);
    if (!clip) return;
    this.oldParams = JSON.parse(JSON.stringify(clip.params));
    this.oldSpeed = clip.speed;
    this._apply(clip, this.partialParams);
    if (this.partialParams.speed !== undefined) clip.speed = this.partialParams.speed;
  }

  undo(tl) {
    const clip = tl.findClip(this.clipId);
    if (!clip) return;
    clip.params = this.oldParams;
    if (this.partialParams.speed !== undefined) clip.speed = this.oldSpeed;
  }

  _apply(clip, partial) {
    if (partial.transform) Object.assign(clip.params.transform, partial.transform);
    if (partial.audio) Object.assign(clip.params.audio, partial.audio);
    if (partial.filters) Object.assign(clip.params.filters, partial.filters);
    if (partial.overlay !== undefined) clip.params.overlay = partial.overlay;
  }
}
