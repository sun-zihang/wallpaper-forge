from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFileInfo, QItemSelectionModel, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QFont, QIcon, QMovie, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileIconProvider,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.styles import ACCENT, BG, BORDER, FAINT, FAIL, MONO_FONT, OK

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv"}
_TYPE_FILTERS = (
    ("全部类型", "all"),
    ("图片", "image"),
    ("视频", "video"),
    ("GIF", "gif"),
    ("壁纸包", "package"),
)
_STATUS_FILTERS = (
    ("全部状态", "all"),
    ("等待", "pending"),
    ("处理中", "running"),
    ("完成", "done"),
    ("失败", "failed"),
    ("已取消", "cancelled"),
)


def _format_size(size_bytes: int) -> str:
    size_kb = max(0, size_bytes) / 1024
    if size_kb < 1024:
        return f"{size_kb:.0f} KB"
    return f"{size_kb / 1024:.1f} MB"


class _PreviewImage(QLabel):
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._source = pixmap
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._fit()

    def _fit(self) -> None:
        if self._source.isNull() or self.width() <= 0 or self.height() <= 0:
            return
        self.setPixmap(
            self._source.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()


_MAX_GIF_PREVIEW_BYTES = 30 * 1024 * 1024


class _PreviewMovie(QLabel):
    def __init__(self, movie: QMovie, parent=None):
        super().__init__(parent)
        self._movie = movie
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        movie.frameChanged.connect(self._on_frame)
        movie.start()

    def _on_frame(self, _frame: int) -> None:
        self._fit()

    def _fit(self) -> None:
        if self.width() <= 0 or self.height() <= 0:
            return
        frame = self._movie.currentImage()
        if frame.isNull():
            return
        pix = QPixmap.fromImage(frame)
        if pix.isNull():
            return
        self.setPixmap(
            pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()


class ImagePreviewDialog(QDialog):
    def __init__(self, image_path: Path, parent=None):
        super().__init__(parent)
        self.image_path = Path(image_path)
        self.movie: QMovie | None = None
        self.preview_kind = "static"
        pixmap = QPixmap(str(self.image_path))
        size_bytes = 0
        try:
            size_bytes = self.image_path.stat().st_size
        except OSError:
            pass
        if (
            self.image_path.suffix.lower() == ".gif"
            and 0 < size_bytes <= _MAX_GIF_PREVIEW_BYTES
        ):
            candidate = QMovie(str(self.image_path))
            if candidate.isValid():
                candidate.setCacheMode(QMovie.CacheAll)
                self.movie = candidate
                self.preview_kind = "movie"
        if self.movie is None and pixmap.isNull():
            raise ValueError(f"无法预览图片：{self.image_path.name}")
        self.setWindowTitle("图片预览")
        self.resize(720, 520)

        layout = QVBoxLayout(self)
        if self.movie is not None:
            self.image = _PreviewMovie(self.movie)
        else:
            self.image = _PreviewImage(pixmap)
        self.image.setObjectName("previewImage")
        self.image.setStyleSheet(f"background: {BG}; border: 1px solid {BORDER};")
        layout.addWidget(self.image, 1)
        if self.movie is not None:
            self.finished.connect(self.movie.stop)

        self.info = QLabel(f"{self.image_path.name}    {_format_size(size_bytes)}")
        self.info.setObjectName("mutedText")
        layout.addWidget(self.info)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText("关闭")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


_STATUS_COLORS = {
    "pending": FAINT,
    "running": ACCENT,
    "done": OK,
    "failed": FAIL,
    "cancelled": FAINT,
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
        self.accept_exts = {
            str(ext).lower() for ext in (accept_exts or (_IMAGE_EXTS | _VIDEO_EXTS))
        }
        self.setAcceptDrops(True)
        self._row_by_key: dict[str, int] = {}
        self._selection_rows: set[int] = set()
        self._filtering = False
        self.output_map: dict[str, Path] = {}
        self._icon_provider = QFileIconProvider(self)
        self._thumbnail_cache: dict[tuple[str, int, int], QIcon] = {}
        self._thumbnail_row_keys: dict[int, tuple[str, int, int]] = {}
        self._preview_dialog: ImagePreviewDialog | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.hint = QLabel("拖拽文件/文件夹到此处，或使用下方按钮添加")
        self.hint.setObjectName("mutedText")
        self.hint.setContentsMargins(4, 4, 4, 4)
        top.addWidget(self.hint, 1)
        self.preview_btn = QPushButton("预览")
        self.preview_btn.setObjectName("secondary")
        self.preview_btn.setEnabled(False)
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.setObjectName("secondary")
        self.invert_btn = QPushButton("反选")
        self.invert_btn.setObjectName("secondary")
        top.addWidget(self.preview_btn)
        top.addWidget(self.select_all_btn)
        top.addWidget(self.invert_btn)
        layout.addLayout(top)

        filters = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索文件名…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumWidth(190)
        filters.addWidget(self.search_edit, 1)
        self.type_filter = QComboBox()
        for label, value in _TYPE_FILTERS:
            self.type_filter.addItem(label, value)
        filters.addWidget(self.type_filter)
        self.status_filter = QComboBox()
        for label, value in _STATUS_FILTERS:
            self.status_filter.addItem(label, value)
        filters.addWidget(self.status_filter)
        layout.addLayout(filters)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["文件", "格式", "大小", "状态", "缩略图"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.horizontalHeader().resizeSection(4, 52)
        self.table.setIconSize(QSize(28, 28))
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self._open_output)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.itemSelectionChanged.connect(self._update_hint)
        self.table.itemSelectionChanged.connect(self._update_preview_state)
        self.table.verticalScrollBar().valueChanged.connect(
            self._load_visible_thumbnails
        )
        self.select_all_btn.clicked.connect(self.select_all)
        self.invert_btn.clicked.connect(self.invert_selection)
        self.preview_btn.clicked.connect(self.preview_selected)
        self.search_edit.textChanged.connect(self._apply_filters)
        self.type_filter.currentIndexChanged.connect(self._apply_filters)
        self.status_filter.currentIndexChanged.connect(self._apply_filters)
        self.files_changed.connect(self._apply_filters)
        layout.addWidget(self.table, 1)
        self._apply_filters()

    @staticmethod
    def _key(p: Path) -> str:
        try:
            return str(p.resolve())
        except OSError:
            return str(p)

    @staticmethod
    def _item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFont(QFont(MONO_FONT))
        return item

    def set_accept_exts(self, exts: set[str]) -> None:
        self.accept_exts = {str(ext).lower() for ext in exts}
        self._apply_filters()

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
            QTimer.singleShot(0, self._load_visible_thumbnails)

    def _append(self, p: Path, existing: set[str]) -> bool:
        key = self._key(p)
        if key in existing:
            return False
        existing.add(key)
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._row_by_key[key] = row
        try:
            size_bytes = p.stat().st_size
        except OSError:
            size_bytes = 0
        self.table.setItem(row, 0, self._item(str(p)))
        self.table.setItem(row, 1, QTableWidgetItem(p.suffix.lstrip(".").upper()))
        self.table.setItem(row, 2, self._item(_format_size(size_bytes)))
        status = self._item("等待")
        status.setData(Qt.UserRole, "pending")
        status.setForeground(QColor(FAINT))
        self.table.setItem(row, 3, status)
        self.table.setItem(row, 4, QTableWidgetItem())
        return True

    def _selection_changed(self) -> None:
        if not self._filtering:
            self._selection_rows = {i.row() for i in self.table.selectedIndexes()}

    def selected_or_all(self) -> list[Path]:
        rows = sorted(self._selection_rows)
        if not rows:
            rows = list(range(self.table.rowCount()))
        return self._paths_at(rows)

    def select_all(self) -> None:
        self._filtering = True
        try:
            self.table.clearSelection()
            model = self.table.model()
            selection = self.table.selectionModel()
            for row in range(self.table.rowCount()):
                selection.select(
                    model.index(row, 0),
                    QItemSelectionModel.Select | QItemSelectionModel.Rows,
                )
            self._selection_rows = set(range(self.table.rowCount()))
        finally:
            self._filtering = False
        self._update_hint()
        self._update_preview_state()

    def invert_selection(self) -> None:
        total = self.table.rowCount()
        current = set(self._selection_rows)
        self._filtering = True
        try:
            self.table.clearSelection()
            model = self.table.model()
            selection = self.table.selectionModel()
            for r in range(total):
                if r not in current:
                    selection.select(
                        model.index(r, 0),
                        QItemSelectionModel.Select | QItemSelectionModel.Rows,
                    )
            self._selection_rows = set(range(total)) - current
        finally:
            self._filtering = False
        self._update_hint()
        self._update_preview_state()

    def _type_for_path(self, path: Path) -> str:
        extension = path.suffix.lower()
        if extension == ".gif":
            return "gif"
        if extension in _IMAGE_EXTS:
            return "image"
        if extension in _VIDEO_EXTS:
            return "video"
        if extension in self.accept_exts:
            return "package"
        return ""

    def _matches_filters(
        self, row: int, search_text: str, type_value: str, status_value: str
    ) -> bool:
        path_item = self.table.item(row, 0)
        status_item = self.table.item(row, 3)
        if not path_item or not status_item:
            return False
        path = Path(path_item.text())
        if search_text and search_text not in path.name.casefold():
            return False
        if type_value != "all" and self._type_for_path(path) != type_value:
            return False
        if status_value != "all" and status_item.data(Qt.UserRole) != status_value:
            return False
        return True

    def _restore_selection(self) -> None:
        self._filtering = True
        try:
            self.table.clearSelection()
            model = self.table.model()
            selection = self.table.selectionModel()
            for row in sorted(self._selection_rows):
                if 0 <= row < self.table.rowCount():
                    selection.select(
                        model.index(row, 0),
                        QItemSelectionModel.Select | QItemSelectionModel.Rows,
                    )
        finally:
            self._filtering = False

    def _apply_filters(self) -> None:
        search_text = self.search_edit.text().strip().casefold()
        type_value = self.type_filter.currentData()
        status_value = self.status_filter.currentData()
        self._filtering = True
        try:
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(
                    row,
                    not self._matches_filters(row, search_text, type_value, status_value),
                )
            self._restore_selection()
        finally:
            self._filtering = False
        self._update_hint()
        self._update_preview_state()
        self._load_visible_thumbnails()

    def _update_hint(self) -> None:
        total = self.table.rowCount()
        if total == 0:
            self.hint.setText("拖拽文件/文件夹到此处，或使用下方按钮添加")
            return
        visible = sum(not self.table.isRowHidden(row) for row in range(total))
        n = len(self._selection_rows)
        if visible == total:
            self.hint.setText(f"已选中 {n}/{total}（未选中则处理全部）")
        else:
            self.hint.setText(
                f"显示 {visible} / 共 {total}；已选中 {n}/{total}（未选中则处理全部）"
            )

    def _selected_preview_path(self) -> Path | None:
        rows = sorted(self._selection_rows)
        if len(rows) != 1:
            return None
        item = self.table.item(rows[0], 0)
        return Path(item.text()) if item else None

    def _update_preview_state(self) -> None:
        path = self._selected_preview_path()
        self.preview_btn.setEnabled(
            path is not None and path.suffix.lower() in _IMAGE_EXTS
        )

    def preview_selected(self) -> None:
        path = self._selected_preview_path()
        if path is None or path.suffix.lower() not in _IMAGE_EXTS:
            return
        if self._preview_dialog is not None:
            self._preview_dialog.close()
        try:
            dialog = ImagePreviewDialog(path, self)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "预览失败", str(exc))
            return
        self._preview_dialog = dialog
        dialog.finished.connect(lambda _: setattr(self, "_preview_dialog", None))
        dialog.show()

    def _thumbnail_key(self, path: Path) -> tuple[str, int, int]:
        try:
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            mtime_ns = 0
        return str(path), mtime_ns, 28

    def _load_visible_thumbnails(self) -> None:
        viewport = self.table.viewport()
        if not viewport.isVisible() or self.table.rowCount() == 0:
            return
        top = self.table.indexAt(QPoint(0, 0)).row()
        if top < 0:
            top = 0
        bottom = self.table.indexAt(viewport.rect().bottomLeft()).row()
        if bottom < top:
            row_height = max(
                1, self.table.rowHeight(top) if top < self.table.rowCount() else 1
            )
            bottom = min(
                self.table.rowCount() - 1,
                top + max(0, viewport.height() // row_height),
            )
        for row in range(top, bottom + 1):
            if row >= self.table.rowCount() or self.table.isRowHidden(row):
                continue
            path_item = self.table.item(row, 0)
            if not path_item:
                continue
            path = Path(path_item.text())
            if path.suffix.lower() not in _IMAGE_EXTS:
                continue
            key = self._thumbnail_key(path)
            if self._thumbnail_row_keys.get(row) == key:
                continue
            icon = self._thumbnail_cache.get(key)
            if icon is None:
                icon = self._icon_provider.icon(QFileInfo(str(path)))
                self._thumbnail_cache[key] = icon
            thumbnail_item = self.table.item(row, 4)
            if thumbnail_item is not None:
                thumbnail_item.setIcon(icon)
            self._thumbnail_row_keys[row] = key

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._load_visible_thumbnails)

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
        self._selection_rows.clear()
        self.output_map.clear()
        self._thumbnail_row_keys.clear()
        self.files_changed.emit()

    def set_status_for_path(self, path: Path, status: str, detail: str = "") -> None:
        key = self._key(path)
        row = self._row_by_key.get(key)
        if row is None:
            for r in range(self.table.rowCount()):
                item = self.table.item(r, 0)
                if item and item.text() == str(path):
                    self._write_status(r, status, detail)
                    self._apply_filters()
                    return
            return
        if 0 <= row < self.table.rowCount():
            self._write_status(row, status, detail)
            self._apply_filters()

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
        item.setForeground(QColor(_STATUS_COLORS.get(status, FAINT)))

    def reset_statuses(self) -> None:
        self.table.setUpdatesEnabled(False)
        try:
            for r in range(self.table.rowCount()):
                self._write_status(r, "pending")
        finally:
            self.table.setUpdatesEnabled(True)
        self._apply_filters()

    def _open_output(self) -> None:
        rows = sorted(self._selection_rows)
        if not rows:
            return
        item = self.table.item(rows[0], 0)
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
