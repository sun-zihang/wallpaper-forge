from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from core.tasks import OutputMode, Task, TaskKind, resolve_outputs
from gui.pages.base import BasePage

_UNPACK_EXTS = {".pkg", ".tex", ".mpkg"}

_KIND_BY_EXT = {
    ".pkg": TaskKind.UNPACK_PKG,
    ".tex": TaskKind.UNPACK_TEX,
    ".mpkg": TaskKind.UNPACK_MPKG,
}


def _out_dir_for(
    src: Path,
    mode: OutputMode,
    unified: Path | None,
    *,
    overwrite: bool = False,
    taken: set[Path] | None = None,
) -> Path:
    stem = src.stem
    if mode is OutputMode.UNIFIED:
        assert unified is not None
        base = unified / stem
    else:
        base = src.parent / "converted" / stem
    if taken is None:
        taken = set()
    if overwrite and base.exists() and base.is_dir() and base.resolve() not in taken:
        taken.add(base.resolve())
        return base
    n = 1
    cand = base
    while True:
        if overwrite:
            conflict = cand.resolve() in taken or (cand.exists() and not cand.is_dir())
        else:
            conflict = cand.resolve() in taken or (
                cand.exists() and (not cand.is_dir() or any(cand.iterdir()))
            )
        if not conflict:
            taken.add(cand.resolve())
            return cand
        cand = base.with_name(f"{stem} ({n})")
        n += 1


class UnpackPage(BasePage):
    def __init__(self):
        super().__init__(_UNPACK_EXTS)

        info = QGroupBox("Wallpaper Engine 专有格式")
        row = QHBoxLayout(info)
        label = QLabel(
            "支持 .pkg 解包、.tex 抽取内嵌图片/视频、.mpkg 提取 MP4。\n"
            "每个源文件输出到独立目录：converted/<文件名>/"
        )
        label.setStyleSheet("color: #aaaaaa;")
        row.addWidget(label)
        row.addStretch(1)

        mid = QWidget()
        layout = QVBoxLayout(mid)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(info)
        layout.addWidget(self.table, 1)
        self.finish_layout(mid)
        self.start_btn.setText("开始解包")
        self.table.set_accept_exts(_UNPACK_EXTS)

    def start_batch(self) -> None:
        paths = [p for p in self._batch_paths() if p.suffix.lower() in _UNPACK_EXTS]
        if not paths:
            QMessageBox.information(self, "提示", "请先添加 .pkg / .tex / .mpkg 文件")
            return
        mode = self.output_mode_value()
        if mode is OutputMode.UNIFIED and self.unified_dir is None:
            return

        ow = self.overwrite_check.isChecked()
        batch: list[Task] = []
        out_dirs: list[Path] = []
        taken: set[Path] = set()
        for p in paths:
            kind = _KIND_BY_EXT[p.suffix.lower()]
            out_dir = _out_dir_for(p, mode, self.unified_dir, overwrite=ow, taken=taken)
            out_dirs.append(out_dir)
            # Pre-create parent so resolve side effects stay consistent
            out_dir.parent.mkdir(parents=True, exist_ok=True)
            batch.append(
                Task(
                    sources=[p],
                    kind=kind,
                    params={"out_dir": out_dir},
                    output_mode=mode,
                    unified_dir=self.unified_dir,
                    outputs=[],
                )
            )
        # out_dirs are directories, so resolve-equality with file sources is structurally impossible (can never fire; correct per design).
        if not self._confirm_overwrite(paths, out_dirs):
            return
        self._submit(batch)
