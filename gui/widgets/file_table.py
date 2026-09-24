from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, Qt, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv"}

_STATUS_COLORS = {
    "pending": "#aaaaaa",
    "running": "#fbbf24",
    "done": "#4ade80",
    "failed": "#f87171",
    "cancelled": "#94a3b8",
}
_STATUS_TEXT = {
    "pending": "等待",
    "running": "处理中",
    "done": "完成",
    "failed": "失败",
    "cancelled": "已取消",
}


class FileTable(QWidget):
    open_output_requested = Signal(Path)
    files_changed = Signal()

    def __init__(self, accept_exts: set[str] | None = None):
        super().__init__()
        self.accept_exts = set(accept_exts or (_IMAGE_EXTS | _VIDEO_EXTS))
        self.setAcceptDrops(True)
        self._row_by_key: dict[str, int] = {}
        self.output_map: dict[str, Path] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.hint = QLabel("拖拽文件/文件夹到此处，或使用下方按钮添加")
        self.hint.setStyleSheet("color: #888888; padding: 4px;")
        top.addWidget(self.hint, 1)
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.setObjectName("secondary")
        self.invert_btn = QPushButton("反选")
        self.invert_btn.setObjectName("secondary")
        top.addWidget(self.select_all_btn)
        top.addWidget(self.invert_btn)
        layout.addLayout(top)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["文件", "格式", "大小", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeToContents
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self._open_output)
        self.table.itemSelectionChanged.connect(self._update_hint)
        self.select_all_btn.clicked.connect(self.select_all)
        self.invert_btn.clicked.connect(self.invert_selection)
        self.files_changed.connect(self._update_hint)
        layout.addWidget(self.table, 1)

    @staticmethod
    def _key(p: Path) -> str:
        try:
            return str(p.resolve())
        except OSError:
            return str(p)

    def set_accept_exts(self, exts: set[str]) -> None:
        self.accept_exts = set(exts)

    def add_paths(self, paths: list[Path]) -> None:
        existing = set(self._row_by_key)
        added = False
        self.table.setUpdatesEnabled(False)
        try:
            for raw in paths:
                p = Path(raw)
                if p.is_dir():
                    for child in sorted(p.rglob("*")):
                        if child.is_file() and child.suffix.lower() in self.accept_exts:
                            added = self._append(child, existing) or added
                elif p.is_file() and p.suffix.lower() in self.accept_exts:
                    added = self._append(p, existing) or added
        finally:
            self.table.setUpdatesEnabled(True)
        if added:
            self.files_changed.emit()

    def _append(self, p: Path, existing: set[str]) -> bool:
        key = self._key(p)
        if key in existing:
            return False
        existing.add(key)
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._row_by_key[key] = row
        try:
            size_kb = p.stat().st_size / 1024
        except OSError:
            size_kb = 0
        size_txt = f"{size_kb:.0f} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"
        self.table.setItem(row, 0, QTableWidgetItem(str(p)))
        self.table.setItem(row, 1, QTableWidgetItem(p.suffix.lstrip(".").upper()))
        self.table.setItem(row, 2, QTableWidgetItem(size_txt))
        status = QTableWidgetItem("等待")
        status.setData(Qt.UserRole, "pending")
        status.setForeground(QColor("#aaaaaa"))
        self.table.setItem(row, 3, status)
        return True

    def selected_or_all(self) -> list[Path]:
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows:
            rows = list(range(self.table.rowCount()))
        return self._paths_at(rows)

    def select_all(self) -> None:
        self.table.selectAll()

    def invert_selection(self) -> None:
        total = self.table.rowCount()
        current = {i.row() for i in self.table.selectedIndexes()}
        self.table.clearSelection()
        model = self.table.model()
        selection = self.table.selectionModel()
        for r in range(total):
            if r not in current:
                selection.select(
                    model.index(r, 0),
                    QItemSelectionModel.Select | QItemSelectionModel.Rows,
                )

    def _update_hint(self) -> None:
        total = self.table.rowCount()
        if total == 0:
            self.hint.setText("拖拽文件/文件夹到此处，或使用下方按钮添加")
            return
        n = len({i.row() for i in self.table.selectedIndexes()})
        self.hint.setText(f"已选中 {n}/{total}（未选中则处理全部）")

    def set_output_map(self, mapping: dict[str, Path]) -> None:
        self.output_map = dict(mapping)

    def all_paths(self) -> list[Path]:
        return self._paths_at(range(self.table.rowCount()))

    def _paths_at(self, rows) -> list[Path]:
        out = []
        for r in rows:
            item = self.table.item(r, 0)
            if item:
                out.append(Path(item.text()))
        return out

    def clear(self) -> None:
        self.table.setRowCount(0)
        self._row_by_key.clear()
        self.output_map.clear()
        self.files_changed.emit()

    def set_status_for_path(self, path: Path, status: str, detail: str = "") -> None:
        key = self._key(path)
        row = self._row_by_key.get(key)
        if row is None:
            # fallback linear scan (path text may differ from resolve key)
            for r in range(self.table.rowCount()):
                item = self.table.item(r, 0)
                if item and item.text() == str(path):
                    self._write_status(r, status, detail)
                    return
            return
        if 0 <= row < self.table.rowCount():
            self._write_status(row, status, detail)

    def _write_status(self, row: int, status: str, detail: str = "") -> None:
        item = self.table.item(row, 3)
        if not item:
            return
        text = _STATUS_TEXT.get(status, status)
        if detail and status == "failed":
            text = f"{text}（{detail}）"
        elif detail and status == "cancelled":
            text = detail
        item.setText(text)
        item.setData(Qt.UserRole, status)
        item.setForeground(QColor(_STATUS_COLORS.get(status, "#aaaaaa")))

    def reset_statuses(self) -> None:
        self.table.setUpdatesEnabled(False)
        try:
            for r in range(self.table.rowCount()):
                self._write_status(r, "pending")
        finally:
            self.table.setUpdatesEnabled(True)

    def _open_output(self) -> None:
        rows = {i.row() for i in self.table.selectedIndexes()}
        if not rows:
            return
        item = self.table.item(next(iter(rows)), 0)
        if not item:
            return
        src_text = item.text()
        out = self.output_map.get(src_text)
        if out is None:
            out = self.output_map.get(self._key(Path(src_text)))
        if out is not None:
            self.open_output_requested.emit(Path(out))
            return
        parent = Path(src_text).parent
        converted = parent / "converted"
        self.open_output_requested.emit(converted if converted.exists() else parent)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = []
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if local:
                paths.append(Path(local))
        if paths:
            self.add_paths(paths)
        event.acceptProposedAction()
