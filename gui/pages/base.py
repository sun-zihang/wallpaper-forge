from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import Signal, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
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
from gui.settings_store import save_settings
from gui.widgets.file_table import FileTable


class BasePage(QWidget):
    def __init__(self, accept_exts: set[str] | None = None):
        super().__init__()
        self._settings: dict = {}
        self.unified_dir: Path | None = None
        self.last_outputs: list[Path] = []
        self._failed_tasks: list = []
        self._retry_paths: list[Path] | None = None
        self._loading_settings = False

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
        self.unified_edit.setObjectName("pathText")
        self.unified_edit.hide()
        self.pick_out_btn = QPushButton("选择输出目录…")
        self.pick_out_btn.setObjectName("secondary")
        self.pick_out_btn.hide()
        self.overwrite_check = QCheckBox("覆盖已存在的输出")
        self.overwrite_check.setToolTip(
            "勾选后允许覆盖已存在的输出文件并复用输出目录；覆盖源文件前会再确认一次"
        )
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
        bottom.addWidget(self.overwrite_check)
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
        self.thread.progress_pct.connect(self._on_progress_pct)
        self.thread.task_finished.connect(self._on_task)
        self.thread.batch_finished.connect(self._on_batch_done)
        self.thread.status_text.connect(self._on_status)
        self._last_ok = 0
        self._last_failed = 0

    def finish_layout(self, mid: QWidget) -> None:
        self.root.addWidget(mid, 1)
        self.root.addWidget(self.progress)
        self.root.addLayout(self._bottom)

    def _mode_changed(self) -> None:
        unified = self.output_mode.currentData() == "unified"
        self.pick_out_btn.setVisible(unified)
        self.unified_edit.setVisible(unified)
        self._persist({"output_mode": self.output_mode.currentData()})

    def _persist(self, patch: dict) -> None:
        if self._loading_settings:
            return
        self._settings.update(patch)
        save_settings(patch)

    def _last_dir(self) -> str:
        return self._settings.get("last_dir") or ""

    def _pick_out(self) -> None:
        dir_ = QFileDialog.getExistingDirectory(
            self, "选择统一输出目录", self._last_dir()
        )
        if dir_:
            self.unified_dir = Path(dir_)
            self.unified_edit.setText(str(self.unified_dir))
            self.unified_edit.show()
            self._persist({"unified_dir": dir_, "last_dir": dir_})

    def output_mode_value(self) -> OutputMode:
        if self.output_mode.currentData() == "unified":
            if self.unified_dir is None:
                QMessageBox.information(self, "提示", "请先选择统一输出目录")
                return OutputMode.BESIDE
            return OutputMode.UNIFIED
        return OutputMode.BESIDE

    def apply_settings(self, settings: dict) -> None:
        self._settings = dict(settings)
        self._loading_settings = True
        try:
            mode = settings.get("output_mode", "beside")
            self.output_mode.blockSignals(True)
            self.output_mode.setCurrentIndex(1 if mode == "unified" else 0)
            self.output_mode.blockSignals(False)
            ud = settings.get("unified_dir") or ""
            if ud:
                self.unified_dir = Path(ud)
                self.unified_edit.setText(ud)
            self._mode_changed()
        finally:
            self._loading_settings = False

    def set_ffmpeg_ok(self, ok: bool) -> None:
        pass

    def _add_files(self) -> None:
        exts = " ".join(f"*{e}" for e in sorted(self.table.accept_exts))
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择文件", self._last_dir(), f"文件 ({exts})"
        )
        if paths:
            self.table.add_paths([Path(p) for p in paths])
            self._persist({"last_dir": str(Path(paths[0]).parent)})

    def _add_dirs(self) -> None:
        dir_ = QFileDialog.getExistingDirectory(self, "选择文件夹", self._last_dir())
        if dir_:
            self.table.add_paths([Path(dir_)])
            self._persist({"last_dir": dir_})

    def _open_path(self, path: Path) -> None:
        p = Path(path)
        if p.is_file():
            subprocess.Popen(["explorer.exe", "/select,", str(p)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def _open_out(self) -> None:
        if self.last_outputs:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_outputs[0].parent)))
        else:
            QMessageBox.information(self, "提示", "还没有已完成的输出文件")

    def _cancel(self) -> None:
        self.thread.cancel()

    def _on_progress(self, i: int, total: int, name: str) -> None:
        # coarse per-file step; fine-grained percent comes from progress_pct
        if total > 0:
            coarse = int((i - 1) * 100 / total)
            if coarse > self.progress.value():
                self.progress.setValue(coarse)

    def _on_progress_pct(self, pct: int) -> None:
        if 0 <= pct <= 100:
            self.progress.setValue(pct)

    def _on_status(self, text: str) -> None:
        win = self.window()
        label = getattr(win, "status_label", None)
        if label is not None:
            label.setText(text)
            return
        status_bar = getattr(win, "statusBar", None)
        if callable(status_bar):
            status_bar().showMessage(text)

    def _on_task(self, task) -> None:
        status = getattr(task, "status", "pending")
        error = getattr(task, "error", "") or ""
        outputs = [
            o for o in (getattr(task, "outputs", []) or []) if isinstance(o, Path)
        ]
        sources = [Path(s) for s in getattr(task, "sources", [])]
        if status == "done":
            for o in outputs:
                if o.is_file():
                    self.last_outputs.append(o)
            if sources and outputs:
                if len(sources) == len(outputs):
                    pairs = list(zip(sources, outputs))
                else:
                    pairs = [(s, outputs[0]) for s in sources]
                mapping = dict(self.table.output_map)
                for s, o in pairs:
                    if o.is_file():
                        mapping[str(s)] = o
                self.table.set_output_map(mapping)
        elif status == "failed":
            self._failed_tasks.append(task)
        for src in sources:
            self.table.set_status_for_path(src, status, error)

    def _on_batch_done(self, ok: int, failed: int) -> None:
        self._last_ok = ok
        self._last_failed = failed
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if failed and not ok:
            # everything cancelled: leave bar as-is, no success dialog
            self.progress.setValue(0)
            self._on_status("已取消")
            return
        self.progress.setValue(100)
        choice = self._ask_batch_done(ok, failed)
        if choice == "retry":
            self._retry_failed()
        elif choice == "open":
            self._open_out()

    def _build_batch_box(
        self, ok: int, failed: int
    ) -> tuple[QMessageBox, QPushButton, QPushButton | None]:
        box = QMessageBox(self)
        box.setWindowTitle("批量完成")
        msg = f"成功 {ok} 个" + (f"，失败/取消 {failed} 个" if failed else "")
        if failed:
            box.setIcon(QMessageBox.Warning)
            box.setText(msg + "。\n可在列表状态列查看详情。")
        else:
            box.setIcon(QMessageBox.Information)
            box.setText(msg + "。")
        open_btn = box.addButton("打开输出文件夹", QMessageBox.ActionRole)
        open_btn.setEnabled(bool(self.last_outputs))
        retry_btn = None
        if failed and self._failed_tasks:
            retry_btn = box.addButton("重试失败项", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Ok)
        return box, open_btn, retry_btn

    def _ask_batch_done(self, ok: int, failed: int) -> str:
        box, open_btn, retry_btn = self._build_batch_box(ok, failed)
        box.exec()
        clicked = box.clickedButton()
        if retry_btn is not None and clicked is retry_btn:
            return "retry"
        if clicked is open_btn:
            return "open"
        return "ok"

    def _batch_paths(self) -> list[Path]:
        if self._retry_paths is not None:
            return list(self._retry_paths)
        return self.table.selected_or_all()

    def _retry_failed(self) -> None:
        if not self._failed_tasks:
            return
        sources: list[Path] = []
        seen: set[str] = set()
        for task in self._failed_tasks:
            for s in task.sources:
                key = str(s)
                if key not in seen:
                    seen.add(key)
                    sources.append(Path(s))
        self._failed_tasks = []
        self._retry_paths = sources
        try:
            self.start_batch()
        finally:
            self._retry_paths = None

    def _submit(self, batch: list[Task]) -> None:
        if not batch:
            QMessageBox.information(self, "提示", "没有可处理的文件")
            return
        if self.thread.isRunning():
            QMessageBox.information(self, "提示", "已有任务在进行中")
            return
        from core.space import free_space_warning

        sources = [Path(s) for t in batch for s in t.sources]
        outputs = [Path(o) for t in batch for o in t.outputs]
        warn = free_space_warning(sources, outputs)
        if warn:
            ret = QMessageBox.question(
                self,
                "磁盘空间可能不足",
                warn,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                return
        self.table.reset_statuses()
        self.progress.setValue(0)
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.last_outputs = []
        self._failed_tasks = []
        self.thread.submit(batch)

    def _confirm_overwrite(self, sources: list[Path], outs: list[Path]) -> bool:
        from core.tasks import would_overwrite_sources

        if not self.overwrite_check.isChecked():
            return True
        pairs = would_overwrite_sources(list(sources), list(outs))
        if not pairs:
            return True
        n = len(pairs)
        ret = QMessageBox.question(
            self,
            "确认覆盖",
            f"将直接覆盖 {n} 个源文件，此操作不可恢复。\n继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return ret == QMessageBox.Yes

    def start_batch(self) -> None:
        raise NotImplementedError
