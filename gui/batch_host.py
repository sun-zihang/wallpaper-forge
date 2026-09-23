from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from core.tasks import Task
from gui.workers import TaskRunner


class BatchThread(QThread):
    progress = Signal(int, int, str)
    task_finished = Signal(object)
    batch_finished = Signal(int, int)
    status_text = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.runner = TaskRunner()
        self.runner.progress.connect(self.progress)
        self.runner.task_finished.connect(self.task_finished)
        self.runner.batch_finished.connect(self.batch_finished)
        self.runner.status_text.connect(self.status_text)
        self._batch: list[Task] = []

    def submit(self, batch: list[Task]) -> None:
        if self.isRunning():
            return
        self._batch = list(batch)
        self.start()

    def cancel(self) -> None:
        self.runner.request_cancel()

    def run(self) -> None:
        self.runner.run_batch(self._batch)
        self._batch = []
