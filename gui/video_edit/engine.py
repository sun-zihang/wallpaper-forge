from __future__ import annotations

import copy

MAX_UNDO = 50


class EditEngine:
    def __init__(self, timeline):
        self.timeline = timeline
        self.undo_stack: list = []
        self.redo_stack: list = []

    def execute(self, command) -> None:
        command.redo(self.timeline)
        self.undo_stack.append(command)
        self.redo_stack = []
        if len(self.undo_stack) > MAX_UNDO:
            self.undo_stack.pop(0)

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        cmd = self.undo_stack.pop()
        cmd.undo(self.timeline)
        self.redo_stack.append(cmd)
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        cmd = self.redo_stack.pop()
        cmd.redo(self.timeline)
        self.undo_stack.append(cmd)
        return True


class SplitClipCommand:
    def __init__(self, clip_id: str, time: float):
        self.clip_id = clip_id
        self.time = time
        self.new_clip_id: str | None = None
        self.original_clip = None

    def redo(self, timeline) -> None:
        clip = timeline.find_clip(self.clip_id)
        if clip is None:
            return
        self.original_clip = clip
        c1, c2 = clip.split_at(self.time)
        self.new_clip_id = c2.id
        track = timeline.get_clip_track(self.clip_id)
        if track is not None:
            track.replace_clip(self.clip_id, [c1, c2])

    def undo(self, timeline) -> None:
        track = timeline.get_clip_track(self.clip_id)
        if track is None or self.original_clip is None:
            return
        track.replace_clip(self.clip_id, [self.original_clip])
        track.remove_clip(self.new_clip_id)


class RemoveClipCommand:
    def __init__(self, clip_id: str):
        self.clip_id = clip_id
        self.removed_clip = None
        self.track_id: str | None = None
        self.index = -1

    def redo(self, timeline) -> None:
        track = timeline.get_clip_track(self.clip_id)
        if track is None:
            return
        self.removed_clip = timeline.find_clip(self.clip_id)
        self.track_id = track.id
        self.index = track.clips.index(self.removed_clip)
        track.remove_clip(self.clip_id)

    def undo(self, timeline) -> None:
        track = next((t for t in timeline.tracks if t.id == self.track_id), None)
        if track is None or self.removed_clip is None:
            return
        track.clips.insert(min(self.index, len(track.clips)), self.removed_clip)
        track.clips.sort(key=lambda c: c.timeline_in)


class MoveClipCommand:
    def __init__(self, clip_id: str, new_track_id: str, new_in: float):
        self.clip_id = clip_id
        self.new_track_id = new_track_id
        self.new_in = new_in
        self.old_track_id: str | None = None
        self.old_in: float | None = None

    def redo(self, timeline) -> None:
        clip = timeline.find_clip(self.clip_id)
        if clip is None:
            return
        old_track = timeline.get_clip_track(self.clip_id)
        if old_track is None:
            return
        self.old_track_id = old_track.id
        self.old_in = clip.timeline_in
        old_track.remove_clip(self.clip_id)
        clip.timeline_in = self.new_in
        new_track = next((t for t in timeline.tracks if t.id == self.new_track_id), None)
        if new_track is not None:
            new_track.add_clip(clip)

    def undo(self, timeline) -> None:
        clip = timeline.find_clip(self.clip_id)
        if clip is None:
            return
        current_track = timeline.get_clip_track(self.clip_id)
        if current_track is not None:
            current_track.remove_clip(self.clip_id)
        clip.timeline_in = self.old_in
        old_track = next((t for t in timeline.tracks if t.id == self.old_track_id), None)
        if old_track is not None:
            old_track.add_clip(clip)


class TrimClipCommand:
    def __init__(self, clip_id: str, new_source_in: float, new_source_out: float):
        self.clip_id = clip_id
        self.new_source_in = new_source_in
        self.new_source_out = new_source_out
        self.old_source_in: float | None = None
        self.old_source_out: float | None = None

    def redo(self, timeline) -> None:
        clip = timeline.find_clip(self.clip_id)
        if clip is None:
            return
        self.old_source_in = clip.source_in
        self.old_source_out = clip.source_out
        clip.source_in = self.new_source_in
        clip.source_out = self.new_source_out

    def undo(self, timeline) -> None:
        clip = timeline.find_clip(self.clip_id)
        if clip is None:
            return
        clip.source_in = self.old_source_in
        clip.source_out = self.old_source_out


class AdjustParamsCommand:
    def __init__(self, clip_id: str, partial_params: dict):
        self.clip_id = clip_id
        self.partial_params = partial_params
        self.old_params = None
        self.old_speed: float | None = None

    def redo(self, timeline) -> None:
        clip = timeline.find_clip(self.clip_id)
        if clip is None:
            return
        self.old_params = copy.deepcopy(clip.params)
        self.old_speed = clip.speed
        self._apply(clip, self.partial_params)
        if "speed" in self.partial_params:
            clip.speed = self.partial_params["speed"]

    def undo(self, timeline) -> None:
        clip = timeline.find_clip(self.clip_id)
        if clip is None:
            return
        clip.params = self.old_params
        if "speed" in self.partial_params:
            clip.speed = self.old_speed

    @staticmethod
    def _apply(clip, partial: dict) -> None:
        if partial.get("transform"):
            clip.params["transform"].update(partial["transform"])
        if partial.get("audio"):
            clip.params["audio"].update(partial["audio"])
        if partial.get("filters"):
            clip.params["filters"].update(partial["filters"])
        if "overlay" in partial:
            clip.params["overlay"] = partial["overlay"]
