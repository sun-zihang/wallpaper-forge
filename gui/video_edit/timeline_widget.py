from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.video_edit.model import TimelineModel, Track

TRACK_HEIGHT = 52
LABEL_WIDTH = 150
RULER_HEIGHT = 26
PIXELS_PER_SECOND = 60
MIN_TIMELINE_SEC = 10.0
CLIP_COLORS = {
    "video": QColor(70, 130, 180),
    "audio": QColor(60, 160, 110),
}
TRACK_NAMES = {"video": "视频轨道", "audio": "音频轨道"}


def format_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    minutes = int(seconds // 60)
    secs = seconds - minutes * 60
    return f"{minutes:02d}:{secs:04.1f}"


def _clip_color(track_type: str) -> QColor:
    return CLIP_COLORS.get(track_type, QColor(120, 120, 130))


class _TrackLabel(QWidget):
    def __init__(self, track: Track, owner: TimelineWidget) -> None:
        super().__init__()
        self._track = track
        self._owner = owner
        self.setFixedHeight(TRACK_HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)
        default_name = TRACK_NAMES.get(track.type, "轨道")
        self.name_label = QLabel(track.name or default_name)
        self.name_label.setObjectName("pathText")
        self.name_label.setWordWrap(True)
        self.mute_btn = QPushButton("静音")
        self.mute_btn.setObjectName("secondary")
        self.mute_btn.setCheckable(True)
        self.mute_btn.setChecked(track.muted)
        self.del_btn = QPushButton("删除")
        self.del_btn.setObjectName("secondary")
        layout.addWidget(self.name_label, 1)
        layout.addWidget(self.mute_btn)
        layout.addWidget(self.del_btn)
        self.mute_btn.clicked.connect(lambda: owner.toggle_mute(track.id))
        self.del_btn.clicked.connect(lambda: owner.remove_track(track.id))


class _TimelineCanvas(QWidget):
    def __init__(self, owner: TimelineWidget) -> None:
        super().__init__()
        self._owner = owner
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def total_width(self) -> int:
        return int(self._owner.timeline.duration_sec(MIN_TIMELINE_SEC) * PIXELS_PER_SECOND) + 40

    def total_height(self) -> int:
        return RULER_HEIGHT + max(1, len(self._owner.timeline.tracks)) * TRACK_HEIGHT

    def resize_for_content(self) -> None:
        self.setFixedSize(self.total_width(), self.total_height())

    def _tick_step(self) -> float:
        for step in (0.5, 1, 2, 5, 10, 15, 30, 60, 120):
            if step * PIXELS_PER_SECOND >= 70:
                return step
        return 120.0

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(24, 26, 30))
        self._paint_ruler(painter)
        self._paint_lanes(painter)
        self._paint_playhead(painter)
        painter.end()

    def _paint_ruler(self, painter: QPainter) -> None:
        painter.fillRect(0, 0, self.width(), RULER_HEIGHT, QColor(30, 33, 38))
        total = self._owner.timeline.duration_sec(MIN_TIMELINE_SEC)
        step = self._tick_step()
        t = 0.0
        while t <= total:
            x = int(t * PIXELS_PER_SECOND)
            painter.setPen(QPen(QColor(120, 128, 140), 1))
            painter.drawLine(x, RULER_HEIGHT - 6, x, RULER_HEIGHT)
            painter.setPen(QColor(154, 163, 176))
            painter.drawText(x + 3, 15, format_time(t))
            t += step
        painter.setPen(QPen(QColor(42, 48, 58), 1))
        painter.drawLine(0, RULER_HEIGHT, self.width(), RULER_HEIGHT)

    def _paint_lanes(self, painter: QPainter) -> None:
        tracks = self._owner.timeline.tracks
        for i, track in enumerate(tracks):
            y0 = RULER_HEIGHT + i * TRACK_HEIGHT
            bg = QColor(28, 31, 36) if i % 2 == 0 else QColor(26, 28, 33)
            painter.fillRect(0, y0, self.width(), TRACK_HEIGHT, bg)
            painter.setPen(QPen(QColor(42, 48, 58), 1))
            painter.drawLine(0, y0 + TRACK_HEIGHT, self.width(), y0 + TRACK_HEIGHT)
            color = _clip_color(track.type)
            for clip in track.clips:
                x0 = int(clip.timeline_in * PIXELS_PER_SECOND)
                w = max(4, int(clip.duration * PIXELS_PER_SECOND))
                y1 = y0 + 6
                h = TRACK_HEIGHT - 12
                selected = clip.id == self._owner.selected_clip_id
                if track.muted:
                    painter.setOpacity(0.45)
                painter.setPen(QPen(color.darker(140), 1))
                painter.setBrush(color.lighter(160) if selected else color)
                painter.drawRoundedRect(x0 + 1, y1, w - 2, h, 5, 5)
                painter.setOpacity(1.0)
                name = clip.source_file.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
                if len(name) > 24:
                    name = name[:23] + "…"
                painter.setPen(
                    QPen(QColor(235, 238, 244), 1)
                    if not selected
                    else QPen(QColor(255, 224, 130), 1)
                )
                painter.drawText(x0 + 6, y1 + h // 2 + 4, name)
                if selected:
                    painter.setPen(QPen(QColor(255, 224, 130), 2))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRoundedRect(x0 + 1, y1, w - 2, h, 5, 5)

    def _paint_playhead(self, painter: QPainter) -> None:
        x = int(self._owner.playhead_sec * PIXELS_PER_SECOND)
        pen = QPen(QColor(235, 80, 80), 2)
        painter.setPen(pen)
        painter.drawLine(x, 0, x, self.height())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(235, 80, 80))
        painter.drawPolygon(
            [
                QPointF(x, 0),
                QPointF(x - 6, 0),
                QPointF(x, 8),
            ]
        )

    def mousePressEvent(self, event) -> None:
        self._owner.handle_mouse_press(event.position())

    def mouseMoveEvent(self, event) -> None:
        self._owner.handle_mouse_move(event.position())

    def mouseReleaseEvent(self, event) -> None:
        self._owner.handle_mouse_release(event.position())

    def mouseDoubleClickEvent(self, event) -> None:
        self._owner.handle_mouse_double_click(event.position())


class TimelineWidget(QWidget):
    clip_selected = Signal(str)
    clip_split_requested = Signal(str, float)
    playhead_moved = Signal(int)
    selection_cleared = Signal()

    def __init__(self, timeline: TimelineModel, parent=None) -> None:
        super().__init__(parent)
        self._timeline = timeline
        self._selected_clip_id: str | None = None
        self._playhead_sec = 0.0
        self._dragging_playhead = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        toolbar = QHBoxLayout()
        self.add_video_btn = QPushButton("添加视频轨道")
        self.add_video_btn.setObjectName("secondary")
        self.add_audio_btn = QPushButton("添加音频轨道")
        self.add_audio_btn.setObjectName("secondary")
        self.time_label = QLabel(format_time(0))
        self.time_label.setObjectName("pathText")
        toolbar.addWidget(self.add_video_btn)
        toolbar.addWidget(self.add_audio_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(self.time_label)
        root.addLayout(toolbar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.labels_col = QWidget()
        self.labels_col.setFixedWidth(LABEL_WIDTH)
        self.labels_layout = QVBoxLayout(self.labels_col)
        self.labels_layout.setContentsMargins(0, RULER_HEIGHT, 0, 0)
        self.labels_layout.setSpacing(0)
        self.labels_layout.addStretch(1)

        self.canvas = _TimelineCanvas(self)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidget(self.canvas)

        body.addWidget(self.labels_col)
        body.addWidget(self.scroll_area, 1)
        root.addLayout(body, 1)

        self.add_video_btn.clicked.connect(lambda: self.add_track("video"))
        self.add_audio_btn.clicked.connect(lambda: self.add_track("audio"))

        self.refresh()

    @property
    def timeline(self) -> TimelineModel:
        return self._timeline

    @property
    def selected_clip_id(self) -> str | None:
        return self._selected_clip_id

    @property
    def playhead_sec(self) -> float:
        return self._playhead_sec

    @property
    def playhead_ms(self) -> int:
        return int(self._playhead_sec * 1000)

    def duration_sec(self, minimum: float = MIN_TIMELINE_SEC) -> float:
        return self._timeline.duration_sec(minimum)

    def set_playhead_ms(self, position_ms: int) -> None:
        self.set_playhead_sec(position_ms / 1000.0)

    def set_playhead_sec(self, seconds: float) -> None:
        total = self.duration_sec()
        seconds = max(0.0, min(seconds, total))
        if abs(seconds - self._playhead_sec) < 1e-6:
            return
        self._playhead_sec = seconds
        self.time_label.setText(format_time(seconds))
        self.canvas.update()
        self.playhead_moved.emit(int(seconds * 1000))

    def select_clip(self, clip_id: str | None) -> None:
        if clip_id is not None and self._timeline.find_clip(clip_id) is None:
            return
        self._selected_clip_id = clip_id
        self.canvas.update()
        if clip_id is not None:
            self.clip_selected.emit(clip_id)
        else:
            self.selection_cleared.emit()

    def add_track(self, track_type: str) -> Track:
        seq = sum(1 for t in self._timeline.tracks if t.type == track_type) + 1
        default_name = f"{TRACK_NAMES.get(track_type, '轨道')} {seq}"
        track = Track(id="", type=track_type, name=default_name)
        self._timeline.add_track(track)
        self.refresh()
        return track

    def remove_track(self, track_id: str) -> None:
        track = next((t for t in self._timeline.tracks if t.id == track_id), None)
        if track is None:
            return
        if any(c.id == self._selected_clip_id for c in track.clips):
            self._selected_clip_id = None
        self._timeline.remove_track(track_id)
        self.refresh()

    def toggle_mute(self, track_id: str) -> None:
        track = next((t for t in self._timeline.tracks if t.id == track_id), None)
        if track is None:
            return
        track.muted = not track.muted
        self.refresh()

    def refresh(self) -> None:
        self._rebuild_labels()
        self.canvas.resize_for_content()
        self.canvas.update()
        self.time_label.setText(format_time(self._playhead_sec))

    def _rebuild_labels(self) -> None:
        while self.labels_layout.count() > 1:
            item = self.labels_layout.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for track in self._timeline.tracks:
            self.labels_layout.insertWidget(
                self.labels_layout.count() - 1, _TrackLabel(track, self)
            )

    def _time_at(self, x: float) -> float:
        return max(0.0, x / PIXELS_PER_SECOND)

    def _clip_at(self, x: float, track_index: int):
        tracks = self._timeline.tracks
        if track_index < 0 or track_index >= len(tracks):
            return None
        t = self._time_at(x)
        for clip in tracks[track_index].clips:
            if clip.timeline_in <= t <= clip.timeline_in + clip.duration:
                return clip
        return None

    def _track_index_at(self, y: float) -> int:
        if y < RULER_HEIGHT:
            return -1
        return int((y - RULER_HEIGHT) // TRACK_HEIGHT)

    def handle_mouse_press(self, pos: QPointF) -> None:
        if pos.y() <= RULER_HEIGHT or abs(pos.x() - self._playhead_sec * PIXELS_PER_SECOND) <= 5:
            self._dragging_playhead = True
            self.set_playhead_sec(self._time_at(pos.x()))
            return
        clip = self._clip_at(pos.x(), self._track_index_at(pos.y()))
        if clip is not None:
            self.select_clip(clip.id)
        else:
            self.select_clip(None)

    def handle_mouse_move(self, pos: QPointF) -> None:
        if self._dragging_playhead:
            self.set_playhead_sec(self._time_at(pos.x()))

    def handle_mouse_release(self, pos: QPointF) -> None:
        self._dragging_playhead = False

    def handle_mouse_double_click(self, pos: QPointF) -> None:
        if pos.y() < RULER_HEIGHT:
            return
        clip = self._clip_at(pos.x(), self._track_index_at(pos.y()))
        if clip is None:
            return
        self.select_clip(clip.id)
        self.clip_split_requested.emit(clip.id, self._playhead_sec)
