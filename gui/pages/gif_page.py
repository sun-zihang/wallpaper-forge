from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.tasks import OutputMode, Task, TaskKind, resolve_out_dir, resolve_outputs
from gui.pages.base import BasePage

_GIF_EXTS = {".gif"}


class GifPage(BasePage):
    def __init__(self):
        super().__init__(_GIF_EXTS | {".png", ".jpg", ".jpeg", ".webp", ".bmp"})

        options = QGroupBox("GIF 选项")
        row = QHBoxLayout(options)
        row.addWidget(QLabel("模式："))
        self.mode = QComboBox()
        self.mode.addItem("拆帧（GIF → 图片序列）", "split")
        self.mode.addItem("合帧（图片 → GIF）", "merge")
        row.addWidget(self.mode)

        self.lbl_step = QLabel("抽稀步长：")
        self.step = QSpinBox()
        self.step.setRange(1, 30)
        self.step.setValue(1)
        row.addWidget(self.lbl_step)
        row.addWidget(self.step)

        self.lbl_dur = QLabel("帧间隔(ms)：")
        self.dur = QSpinBox()
        self.dur.setRange(10, 5000)
        self.dur.setValue(100)
        row.addWidget(self.lbl_dur)
        row.addWidget(self.dur)

        self.reverse = QCheckBox("倒放")
        row.addWidget(self.reverse)
        self.loop = QCheckBox("无限循环")
        self.loop.setChecked(True)
        row.addWidget(self.loop)

        row.addStretch(1)
        self.mode.currentIndexChanged.connect(self._sync)
        self._sync()

        mid = QWidget()
        layout = QVBoxLayout(mid)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(options)
        layout.addWidget(self.table, 1)
        self.finish_layout(mid)

    def _sync(self) -> None:
        is_split = self.mode.currentData() == "split"
        self.lbl_step.setVisible(is_split)
        self.step.setVisible(is_split)
        self.lbl_dur.setVisible(not is_split)
        self.dur.setVisible(not is_split)
        self.reverse.setVisible(not is_split)
        self.loop.setVisible(not is_split)
        if is_split:
            self.table.set_accept_exts({".gif"})
            self.start_btn.setText("开始拆帧")
        else:
            self.table.set_accept_exts(
                {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
            )
            self.start_btn.setText("开始合帧")

    def start_batch(self) -> None:
        paths = self._batch_paths()
        out_mode = self.output_mode_value()
        if out_mode is OutputMode.UNIFIED and self.unified_dir is None:
            return
        if self.mode.currentData() == "split":
            gifs = [p for p in paths if p.suffix.lower() == ".gif"]
            if not gifs:
                QMessageBox.information(self, "提示", "请先添加 GIF 文件")
                return
            ow = self.overwrite_check.isChecked()
            batch = []
            out_dirs: list[Path] = []
            taken: set[Path] = set()
            for p in gifs:
                out_dir = resolve_out_dir(
                    p,
                    out_mode,
                    self.unified_dir,
                    name_suffix="_frames",
                    overwrite=ow,
                    taken=taken,
                )
                out_dirs.append(out_dir)
                batch.append(
                    Task(
                        sources=[p],
                        kind=TaskKind.GIF_SPLIT,
                        params={"step": self.step.value(), "out_dir": out_dir},
                        output_mode=out_mode,
                        unified_dir=self.unified_dir,
                        outputs=[],
                    )
                )
            # out_dirs are directories, so resolve-equality with file sources is structurally impossible (can never fire; correct per design).
            if not self._confirm_overwrite(gifs, out_dirs):
                return
            self._submit(batch)
        else:
            imgs = [
                p
                for p in paths
                if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
            ]
            if len(imgs) < 1:
                QMessageBox.information(self, "提示", "请先添加图片序列（按文件名排序）")
                return
            imgs = sorted(imgs, key=lambda p: p.name)
            if len(imgs) == 1 and imgs[0].suffix.lower() == ".gif":
                QMessageBox.information(self, "提示", "合帧需要多张图片")
                return
            # merge all into one gif named after first frame stem
            base_src = imgs[0]
            outs = resolve_outputs(
                [base_src], ".gif", out_mode, self.unified_dir,
                overwrite=self.overwrite_check.isChecked(),
            )
            if not self._confirm_overwrite(imgs, outs):
                return
            task = Task(
                sources=imgs,
                kind=TaskKind.GIF_MERGE,
                params={
                    "duration_ms": self.dur.value(),
                    "loop": 0 if self.loop.isChecked() else 1,
                    "reverse": self.reverse.isChecked(),
                },
                output_mode=out_mode,
                unified_dir=self.unified_dir,
                outputs=outs,
            )
            self._submit([task])
