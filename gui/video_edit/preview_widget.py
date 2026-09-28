from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QVBoxLayout, QWidget


class PreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)

        self._video_widget = QVideoWidget(self)
        self._player.setVideoOutput(self._video_widget)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._video_widget)

    def play(self):
        self._player.play()

    def pause(self):
        self._player.pause()

    def seek(self, position_ms: int):
        self._player.setPosition(position_ms)

    def set_volume(self, volume: float):
        self._audio_output.setVolume(volume)

    def set_source(self, file_path: str):
        self._player.setSource(QUrl.fromLocalFile(file_path))

    def get_player(self) -> QMediaPlayer:
        return self._player
