from __future__ import annotations

import contextlib
import os
import tempfile

from core.video_ops import VideoOpError, run_ffmpeg
from gui.video_edit.filters import needs_processing


class NativeExporter:
    def __init__(self, ffmpeg_path: str | None = None):
        self.ffmpeg_path = ffmpeg_path

    def export(self, timeline, settings: dict, on_progress=None, cancel_event=None) -> bytes:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = self._build_plan(timeline)
            intermediates = []

            try:
                for i, clip in enumerate(plan["clips"]):
                    if cancel_event and cancel_event.is_set():
                        raise VideoOpError("已取消")
                    pct = int((i / len(plan["clips"])) * 50)
                    if on_progress:
                        on_progress(pct, f"预处理片段 {i + 1}/{len(plan['clips'])}")

                    if clip.get("needs_processing"):
                        out = os.path.join(tmpdir, f"prep_{i}.mp4")
                        self._process_clip(clip, out, settings, on_progress, cancel_event)
                        intermediates.append(out)
                        clip["processed_file"] = out

                if cancel_event and cancel_event.is_set():
                    raise VideoOpError("已取消")
                if on_progress:
                    on_progress(50, "合成最终视频…")
                output = os.path.join(tmpdir, f"output.{settings.get('format', 'mp4')}")
                self._compose(plan, output, settings, on_progress, cancel_event)
                intermediates.append(output)

                if on_progress:
                    on_progress(100, "导出完成")
                with open(output, "rb") as f:
                    return f.read()
            finally:
                for name in intermediates:
                    with contextlib.suppress(OSError):
                        os.remove(name)

    def _build_plan(self, timeline) -> dict:
        clips = []
        for track in timeline.tracks:
            if track.type != "video" or track.muted:
                continue
            for clip in track.clips:
                clip_dict = clip.to_dict()
                clip_dict["needs_processing"] = needs_processing(clip_dict)
                clip_dict["processed_file"] = None
                clips.append(clip_dict)
        clips.sort(key=lambda c: c["timeline_in"])
        return {"clips": clips}

    def _process_clip(self, clip, out_path, settings, on_progress, cancel_event):
        args = ["-i", clip["source_file"]]
        args += ["-ss", str(clip["source_in"]), "-t", str(clip["source_out"] - clip["source_in"])]
        filter_str = self._build_filter(clip)
        if filter_str:
            args += ["-vf", filter_str]
        audio = clip["params"]["audio"]
        if audio["volume"] != 1.0:
            args += ["-af", f"volume={audio['volume']}"]
        args += ["-c:v", settings.get("video_codec", "libx264")]
        args += ["-preset", settings.get("preset", "veryfast")]
        args += ["-crf", str(settings.get("crf", 23))]
        args += ["-pix_fmt", "yuv420p"]
        args += ["-c:a", settings.get("audio_codec", "aac"), "-ar", "48000", "-ac", "2"]
        args += [out_path]
        run_ffmpeg(
            args,
            cancel_event=cancel_event,
            progress_cb=lambda p: on_progress(p) if on_progress else None,
        )

    def _compose(self, plan, out_path, settings, on_progress, cancel_event):
        clips = plan["clips"]
        if len(clips) == 1:
            src = clips[0].get("processed_file") or clips[0]["source_file"]
            run_ffmpeg(["-i", src, "-c", "copy", out_path], cancel_event=cancel_event)
            return
        concat_file = os.path.join(os.path.dirname(out_path), "concat.txt")
        with open(concat_file, "w") as f:
            for c in clips:
                f.write(f"file '{c.get('processed_file') or c['source_file']}'\n")
        args = ["-f", "concat", "-safe", "0", "-i", concat_file]
        args += ["-c:v", settings.get("video_codec", "libx264")]
        args += ["-preset", settings.get("preset", "veryfast")]
        args += ["-crf", str(settings.get("crf", 23))]
        args += ["-pix_fmt", "yuv420p"]
        args += ["-c:a", settings.get("audio_codec", "aac"), "-ar", "48000", "-ac", "2"]
        args += [out_path]
        run_ffmpeg(
            args,
            cancel_event=cancel_event,
            progress_cb=lambda p: on_progress(p) if on_progress else None,
        )

    def _build_filter(self, clip) -> str:
        from gui.video_edit.filters import build_clip_filter

        return build_clip_filter(clip, 0, 0)
