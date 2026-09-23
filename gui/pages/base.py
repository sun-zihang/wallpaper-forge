from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.tasks import OutputMode, Task
from gui.batch_host import BatchThread
from gui.widgets.file_table import FileTable


class BasePage(QWidget):
    def __init__(self, accept_exts: set[str] | None = None):
        super().__init__()
        self._settings: dict = {}
        self.unified_dir: Path | None = None
        self.last_outputs: list[Path] = []

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(16, 16, 16, 16)
        self.root.setSpacing(10)

        self.table = FileTable(accept_exts)

        bottom = QHBoxLayout()
        self.add_files_btn = QPushButton("添加文件")
        self.add_files_btn.setObjectName("secondary")
        self.add_dir_btn = QPushButton("添加文件夹")
        self.add_dir_btn.setObjectName("secondary")
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setObjectName("secondary")
        self.output_mode = QComboBox()
        self.output_mode.addItem("输出到源旁 converted 子目录", "beside")
        self.output_mode.addItem("输出到统一目录", "unified")
        self.unified_edit = QLabel("")
        self.unified_edit.setStyleSheet("color: #888888;")
        self.unified_edit.hide()
        self.pick_out_btn = QPushButton("选择输出目录…")
        self.pick_out_btn.setObjectName("secondary")
        self.pick_out_btn.hide()
        self.start_btn = QPushButton("开始转换")
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.setEnabled(False)
        self.open_out_btn = QPushButton("打开输出文件夹")
        self.open_out_btn.setObjectName("secondary")

        bottom.addWidget(self.add_files_btn)
        bottom.addWidget(self.add_dir_btn)
        bottom.addWidget(self.clear_btn)
        bottom.addSpacing(12)
        bottom.addWidget(QLabel("输出："))
        bottom.addWidget(self.output_mode)
        bottom.addWidget(self.pick_out_btn)
        bottom.addWidget(self.unified_edit)
        bottom.addStretch(1)
        bottom.addWidget(self.open_out_btn)
        bottom.addWidget(self.cancel_btn)
        bottom.addWidget(self.start_btn)
        self._bottom = bottom

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        self.add_files_btn.clicked.connect(self._add_files)
        self.add_dir_btn.clicked.connect(self._add_dirs)
        self.clear_btn.clicked.connect(self.table.clear)
        self.output_mode.currentIndexChanged.connect(self._mode_changed)
        self.pick_out_btn.clicked.connect(self._pick_out)
        self.open_out_btn.clicked.connect(self._open_out)
        self.start_btn.clicked.connect(self.start_batch)
        self.cancel_btn.clicked.connect(self._cancel)
        self.table.open_output_requested.connect(self._open_path)

        self.thread = BatchThread(self)
        self.thread.progress.connect(self._on_progress)
        self.thread.task_finished.connect(self._on_task)
        self.thread.batch_finished.connect(self._on_batch_done)
        self.thread.status_text.connect(self._on_status)

    def finish_layout(self, mid: QWidget) -> None:
        self.root.addWidget(mid, 1)
        self.root.addWidget(self.progress)
        self.root.addLayout(self._bottom)

    def _mode_changed(self) -> None:
        unified = self.output_mode.currentData() == "unified"
        self.pick_out_btn.setVisible(unified)
        self.unified_edit.setVisible(unified)

    def _pick_out(self) -> None:
        dir_ = QFileDialog.getExistingDirectory(self, "选择统一输出目录")
        if dir_:
            self.unified_dir = Path(dir_)
            self.unified_edit.setText(str(self.unified_dir))
            self.unified_edit.show()

    def output_mode_value(self) -> OutputMode:
        if self.output_mode.currentData() == "unified":
            if self.unified_dir is None:
                QMessageBox.information(self, "提示", "请先选择统一输出目录")
                return OutputMode.BESIDE
            return OutputMode.UNIFIED
        return OutputMode.BESIDE

    def apply_settings(self, settings: dict) -> None:
        self._settings = dict(settings)
        mode = settings.get("output_mode", "beside")
        self.output_mode.blockSignals(True)
        self.output_mode.setCurrentIndex(1 if mode == "unified" else 0)
        self.output_mode.blockSignals(False)
        ud = settings.get("unified_dir") or ""
        if ud:
            self.unified_dir = Path(ud)
            self.unified_edit.setText(ud)
        self._mode_changed()

    def set_ffmpeg_ok(self, ok: bool) -> None:
        pass

    def _add_files(self) -> None:
        exts = " ".join(f"*{e}" for e in sorted(self.table.accept_exts))
        paths, _ = QFileDialog.getOpenFileNames(self, "选择文件", "", f"文件 ({exts})")
        if paths:
            self.table.add_paths([Path(p) for p in paths])

    def _add_dirs(self) -> None:
        dir_ = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if dir_:
            self.table.add_paths([Path(dir_)])

    def _open_path(self, path: Path) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_out(self) -> None:
        if self.last_outputs:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_outputs[0].parent)))
        else:
            QMessageBox.information(self, "提示", "还没有已完成的输出文件")

    def _cancel(self) -> None:
        self.thread.cancel()

    def _on_progress(self, i: int, total: int, name: str) -> None:
        if total > 0:
            self.progress.setValue(int(i * 100 / total))

    def _on_status(self, text: str) -> None:
        win = self.window()
        label = getattr(win, "status_label", None)
        if label is not None:
            label.setText(text)

    def _on_task(self, task) -> None:
        status = getattr(task, "status", "pending")
        error = getattr(task, "error", "") or ""
        outputs = getattr(task, "outputs", []) or []
        if status == "done":
            for o in outputs:
                if isinstance(o, Path) and o.is_file():
                    self.last_outputs.append(o)
        for src in getattr(task, "sources", []):
            self.table.set_status_for_path(Path(src), status, error)

    def _on_batch_done(self, ok: int, failed: int) -> None:
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setValue(100)
        msg = f"成功 {ok} 个" + (f"，失败/取消 {failed} 个" if failed else "")
        if failed:
            QMessageBox.warning(self, "批量完成", msg + "。\n可在列表状态列查看详情。")
        else:
            QMessageBox.information(self, "批量完成", msg + "。")

    def _submit(self, batch: list[Task]) -> None:
        if not batch:
            QMessageBox.information(self, "提示", "没有可处理的文件")
            return
        if self.thread.isRunning():
            QMessageBox.information(self, "提示", "已有任务在进行中")
            return
        self.table.reset_statuses()
        self.progress.setValue(0)
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.last_outputs = []
        self.thread.submit(batch)

    def start_batch(self) -> None:
        raise NotImplementedError
