from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field

_id_counter = 0


def _gen_id(prefix: str) -> str:
    global _id_counter
    _id_counter += 1
    return f"{prefix}_{_id_counter}_{int(time.time() * 1000)}"


def create_default_params() -> dict:
    return {
        "transform": {
            "rotation": 0,
            "flip_h": False,
            "flip_v": False,
            "scale": 1.0,
            "crop": None,
        },
        "audio": {
            "volume": 1.0,
            "fade_in": 0,
            "fade_out": 0,
            "detune": 0,
        },
        "overlay": None,
        "filters": {
            "brightness": 0,
            "contrast": 0,
            "saturation": 0,
            "hue": 0,
            "grayscale": False,
            "sepia": False,
            "blur": 0,
            "sharpen": 0,
        },
    }


@dataclass
class Clip:
    id: str
    source_file: str
    timeline_in: float
    source_in: float
    source_out: float
    speed: float = 1.0
    params: dict = field(default_factory=create_default_params)

    def __post_init__(self):
        if not self.id:
            self.id = _gen_id("clip")

    @property
    def duration(self) -> float:
        return (self.source_out - self.source_in) / self.speed

    def split_at(self, time: float) -> tuple[Clip, Clip]:
        split_source = self.source_in + time * self.speed
        c1 = Clip(
            id=self.id,
            source_file=self.source_file,
            timeline_in=self.timeline_in,
            source_in=self.source_in,
            source_out=split_source,
            speed=self.speed,
            params=copy.deepcopy(self.params),
        )
        c2 = Clip(
            id=_gen_id("clip"),
            source_file=self.source_file,
            timeline_in=self.timeline_in + c1.duration,
            source_in=split_source,
            source_out=self.source_out,
            speed=self.speed,
            params=copy.deepcopy(self.params),
        )
        return c1, c2

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_file": self.source_file,
            "timeline_in": self.timeline_in,
            "source_in": self.source_in,
            "source_out": self.source_out,
            "speed": self.speed,
            "params": self.params,
        }


@dataclass
class Track:
    id: str
    type: str
    name: str = ""
    clips: list[Clip] = field(default_factory=list)
    muted: bool = False
    locked: bool = False
    visible: bool = True

    def __post_init__(self):
        if not self.id:
            self.id = _gen_id("track")

    def add_clip(self, clip: Clip) -> None:
        self.clips.append(clip)
        self.clips.sort(key=lambda c: c.timeline_in)

    def remove_clip(self, clip_id: str) -> None:
        self.clips = [c for c in self.clips if c.id != clip_id]

    def replace_clip(self, old_id: str, new_clips: list[Clip]) -> None:
        idx = next((i for i, c in enumerate(self.clips) if c.id == old_id), -1)
        if idx == -1:
            return
        self.clips[idx:idx + 1] = new_clips
        self.clips.sort(key=lambda c: c.timeline_in)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "clips": [c.to_dict() for c in self.clips],
            "muted": self.muted,
            "locked": self.locked,
            "visible": self.visible,
        }


@dataclass
class TimelineModel:
    id: str
    name: str = "未命名"
    tracks: list[Track] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = _gen_id("timeline")

    @property
    def duration(self) -> float:
        max_end = 0.0
        for track in self.tracks:
            for clip in track.clips:
                end = clip.timeline_in + clip.duration
                if end > max_end:
                    max_end = end
        return max_end

    def duration_sec(self, minimum: float = 0.0) -> float:
        return max(self.duration, minimum)

    def add_track(self, track: Track) -> None:
        self.tracks.append(track)

    def remove_track(self, track_id: str) -> None:
        self.tracks = [t for t in self.tracks if t.id != track_id]

    def find_clip(self, clip_id: str) -> Clip | None:
        for track in self.tracks:
            for clip in track.clips:
                if clip.id == clip_id:
                    return clip
        return None

    def get_clip_track(self, clip_id: str) -> Track | None:
        for track in self.tracks:
            if any(c.id == clip_id for c in track.clips):
                return track
        return None

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "id": self.id,
            "name": self.name,
            "tracks": [t.to_dict() for t in self.tracks],
        }

    @classmethod
    def from_dict(cls, data: dict) -> TimelineModel:
        tracks = []
        for tdata in data.get("tracks", []):
            track = Track(
                id=tdata["id"],
                type=tdata["type"],
                name=tdata.get("name", ""),
                muted=tdata.get("muted", False),
                locked=tdata.get("locked", False),
                visible=tdata.get("visible", True),
            )
            for cdata in tdata.get("clips", []):
                clip = Clip(
                    id=cdata["id"],
                    source_file=cdata["source_file"],
                    timeline_in=cdata["timeline_in"],
                    source_in=cdata["source_in"],
                    source_out=cdata["source_out"],
                    speed=cdata.get("speed", 1.0),
                    params=cdata.get("params", create_default_params()),
                )
                track.clips.append(clip)
            track.clips.sort(key=lambda c: c.timeline_in)
            tracks.append(track)
        return cls(id=data.get("id", ""), name=data.get("name", "未命名"), tracks=tracks)
