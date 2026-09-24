from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.ffmpeg_finder import ffmpeg_available
from core.rewatermark import (
    RewatermarkError,
    extract_preview_frame,
)
from core.tasks import OutputMode, Task, TaskKind
from gui.dialogs_boxselect import BoxSelectDialog
from gui.pages.base import BasePage

_IMG = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
_VID = {".mp4", ".webm", ".mov", ".mkv"}
_ALL = _IMG | _VID


def _clean_out(
    src: Path, ext: str, mode: OutputMode, unified: Path | None, *, overwrite: bool = False
) -> Path:
    """Output path with _clean suffix; overwrite skips exists-renaming."""
    stem = f"{src.stem}_clean"
    if mode is OutputMode.UNIFIED:
        assert unified is not None
        base = unified / f"{stem}.{ext}"
    else:
        base = src.parent / "converted" / f"{stem}.{ext}"
    if overwrite:
        return base
    n = 1
    while base.exists() and base.resolve() == src.resolve():
        base = base.with_name(f"{stem} ({n}).{ext}")
        n += 1
    if base.exists() and base.resolve() != src.resolve():
        while base.exists():
            base = base.with_name(f"{stem} ({n}).{ext}")
            n += 1
    if base.resolve() == src.resolve():
        base = base.with_name(f"{stem}_out.{ext}")
    return base


class RewatermarkPage(BasePage):
    def __init__(self):
        super().__init__(_ALL)

        self._boxes: dict[Path, list[tuple[int, int, int, int]]] = {}
        self._ffmpeg_ok = True

        top = QGroupBox("去水印")
        row = QHBoxLayout(top)
        self.banner = QLabel("未检测到 ffmpeg，视频去水印不可用（图片仍可用）。")
        self.banner.setObjectName("banner")
        self.banner.hide()
        info = QLabel(
            "选中文件 →「框选区域」在预览上拖出一个或多个矩形 → 开始处理。\n"
            "图片用内容修复；视频对整段应用同一区域。输出为 <原名>_clean.*"
        )
        info.setObjectName("mutedText")
        row.addWidget(info)
        row.addStretch(1)

        tools = QHBoxLayout()
        self.select_btn = QPushButton("框选区域…")
        self.select_btn.setObjectName("secondary")
        self.boxes_label = QLabel("未框选")
        self.boxes_label.setObjectName("mutedText")
        tools.addWidget(self.select_btn)
        tools.addWidget(self.boxes_label)
        tools.addStretch(1)
        self._tools_row = tools

        self.select_btn.clicked.connect(self._select_boxes)

        mid = QWidget()
        layout = QVBoxLayout(mid)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.banner)
        layout.addWidget(top)
        layout.addLayout(tools)
        layout.addWidget(self.table, 1)
        self.finish_layout(mid)
        self.start_btn.setText("开始处理")
        self.table.set_accept_exts(_ALL)
        self.table.table.itemSelectionChanged.connect(self._selection_changed)

    def set_ffmpeg_ok(self, ok: bool) -> None:
        self._ffmpeg_ok = ok
        self.banner.setVisible(not ok)

    def _selection_changed(self) -> None:
        paths = self.table.selected_or_all()
        if len(paths) == 1:
            n = len(self._boxes.get(paths[0], []))
            self.boxes_label.setText(
                f"当前文件已框选 {n} 个区域" if n else "当前文件未框选"
            )
        else:
            self.boxes_label.setText("选中单个文件可查看/编辑框选")

    def _current_file(self) -> Path | None:
        rows = {i.row() for i in self.table.table.selectedIndexes()}
        if len(rows) != 1:
            QMessageBox.information(self, "提示", "请先在列表中选中一个文件")
            return None
        item = self.table.table.item(next(iter(rows)), 0)
        return Path(item.text()) if item else None

    def _select_boxes(self) -> None:
        src = self._current_file()
        if src is None:
            return
        is_video = src.suffix.lower() in _VID
        if is_video and not ffmpeg_available():
            QMessageBox.warning(self, "提示", "未找到 ffmpeg，无法提取视频预览帧")
            return

        preview = src
        if is_video:
            cache = src.parent / "converted" / f"{src.stem}_preview.jpg"
            try:
                preview = extract_preview_frame(src, cache)
            except RewatermarkError as e:
                QMessageBox.warning(self, "预览失败", str(e))
                return
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(self, "预览失败", f"视频处理失败：{e}")
                return

        title = "框选水印区域（视频：应用到整段）" if is_video else "框选水印区域"
        boxes = BoxSelectDialog.get_boxes(self, preview, title)
        if boxes is None:
            return
        self._boxes[src] = boxes
        self.boxes_label.setText(f"当前文件已框选 {len(boxes)} 个区域")

    def start_batch(self) -> None:
        paths = [p for p in self._batch_paths() if p.suffix.lower() in _ALL]
        if not paths:
            QMessageBox.information(self, "提示", "请先添加文件")
            return
        missing = [p for p in paths if not self._boxes.get(p)]
        if missing:
            QMessageBox.information(
                self,
                "提示",
                f"以下文件还没有框选区域：\n"
                + "\n".join(p.name for p in missing[:5])
                + ("…" if len(missing) > 5 else ""),
            )
            return

        videos = [p for p in paths if p.suffix.lower() in _VID]
        if videos and not ffmpeg_available():
            QMessageBox.warning(self, "提示", "未找到 ffmpeg，无法处理视频")
            return

        mode = self.output_mode_value()
        if mode is OutputMode.UNIFIED and self.unified_dir is None:
            return

        batch: list[Task] = []
        ow = self.overwrite_check.isChecked()
        for p in paths:
            boxes = self._boxes[p]
            if p.suffix.lower() in _VID:
                # frame size probed inside worker (never block UI thread)
                out = _clean_out(p, "mp4", mode, self.unified_dir, overwrite=ow)
                batch.append(
                    Task(
                        sources=[p],
                        kind=TaskKind.REMOVE_VIDEO_WATERMARK,
                        params={"boxes": boxes, "out": out},
                        output_mode=mode,
                        unified_dir=self.unified_dir,
                        outputs=[out],
                    )
                )
            else:
                out = _clean_out(p, "png", mode, self.unified_dir, overwrite=ow)
                batch.append(
                    Task(
                        sources=[p],
                        kind=TaskKind.INPAINT_IMAGE,
                        params={"boxes": boxes, "out": out},
                        output_mode=mode,
                        unified_dir=self.unified_dir,
                        outputs=[out],
                    )
                )
        outs = [t.outputs[0] for t in batch]
        if not self._confirm_overwrite(paths, outs):
            return
        self._submit(batch)
