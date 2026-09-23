# Wallpaper Forge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Chinese-language Windows desktop app that batch-converts wallpaper images/videos between common formats with crop, watermark, and GIF tools, packaged as a Setup installer and published to GitHub.

**Architecture:** Three layers — pure-Python `core/` (no Qt), `gui/` (PySide6 pages + one BatchWorker QThread), `build/` (PyInstaller onedir + Inno Setup). Video paths shell out to a bundled `ffmpeg.exe` located by `ffmpeg_finder`.

**Tech Stack:** Python 3.11+ (local: 3.13), PySide6, Pillow, pytest, PyInstaller, Inno Setup, ffmpeg (bundled binary).

## Global Constraints

- UI language: Simplified Chinese only; no i18n framework.
- `core/` must never import Qt (`PySide6`); GUI-only code lives under `gui/`.
- Never overwrite source files; output defaults to `<source_dir>/converted/<stem>.<ext>`; optional unified output dir; collisions get ` (1)`, ` (2)` suffixes.
- Supported image formats: PNG, JPG, WebP, BMP, GIF (still). Video: MP4, WebM, MOV, MKV ↔ convert; video→GIF; frame extract; trim.
- ffmpeg lookup order: directory of running exe → env `WALLPAPER_FORGE_FFMPEG` → `PATH` → `vendor/ffmpeg/ffmpeg.exe` (repo) / `imageio_ffmpeg` fallback in dev.
- Repo name: `wallpaper-forge` (GitHub public); product name: WallpaperConverter; version single-sourced in `core/version.py` as `__version__ = "0.1.0"`.
- Tests: pytest against `core/` only, no GUI tests. Every task ends green before the next starts.
- Commit after each task with conventional message (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).

---

### Task 1: Scaffold + Task model + output paths

**Files:**
- Create: `requirements.txt`, `core/__init__.py`, `core/version.py`, `core/tasks.py`, `main.py`, `tests/__init__.py`, `tests/conftest.py`, `tests/test_tasks.py`

**Interfaces:**
- Produces: `core.version.__version__: str`
- Produces: `core.tasks.OutputMode` (`enum.Enum`: `BESIDE = "beside"`, `UNIFIED = "unified"`)
- Produces: `core.tasks.TaskKind` (`enum.Enum`: `IMAGE_CONVERT`, `VIDEO_CONVERT`, `VIDEO_TO_GIF`, `VIDEO_EXTRACT_FRAMES`, `VIDEO_TRIM`, `GIF_SPLIT`, `GIF_MERGE`, `IMAGE_EDIT`)
- Produces: `core.tasks.Task` dataclass: fields `sources: list[Path]`, `kind: TaskKind`, `params: dict`, `output_mode: OutputMode`, `unified_dir: Path | None`, `outputs: list[Path]` (filled by `resolve_outputs`), `status: str` (`"pending"`), `error: str | None`
- Produces: `core.tasks.resolve_outputs(sources, ext, output_mode, unified_dir, op_subdir="converted") -> list[Path]` — beside mode puts files in `src.parent/op_subdir/stem.ext`; unified puts `unified_dir/stem.ext`; each call must not collide with existing files **or paths already returned in the same batch** (suffix ` (n)` before ext)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_tasks.py
from pathlib import Path
from core.tasks import OutputMode, resolve_outputs

def test_beside_mode_creates_converted_subdir_path(tmp_path: Path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    outs = resolve_outputs([src], "jpg", OutputMode.BESIDE, None)
    assert outs == [tmp_path / "converted" / "a.jpg"]

def test_unified_mode_uses_dir(tmp_path: Path):
    src = tmp_path / "a.png"
    outdir = tmp_path / "out"
    outs = resolve_outputs([src], "png", OutputMode.UNIFIED, outdir)
    assert outs == [outdir / "a.png"]

def test_batch_name_collision_gets_suffix(tmp_path: Path):
    a = tmp_path / "a.png"
    b = tmp_path / "sub" / "a.png"
    b.parent.mkdir()
    a.write_bytes(b"1"); b.write_bytes(b"2")
    outs = resolve_outputs([a, b], "jpg", OutputMode.UNIFIED, tmp_path / "out")
    assert outs[0].name == "a.jpg"
    assert outs[1].name == "a (1).jpg"

def test_never_points_at_source_file(tmp_path: Path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    outs = resolve_outputs([src], "png", OutputMode.UNIFIED, tmp_path)
    assert outs[0] != src
    assert outs[0].name == "a (1).png"
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/test_tasks.py -v`

- [ ] **Step 3: Implement**

```python
# core/version.py
__version__ = "0.1.0"

# core/tasks.py
from __future__ import annotations
import enum
from dataclasses import dataclass, field
from pathlib import Path

class OutputMode(enum.Enum):
    BESIDE = "beside"
    UNIFIED = "unified"

class TaskKind(enum.Enum):
    IMAGE_CONVERT = "image_convert"
    IMAGE_EDIT = "image_edit"
    VIDEO_CONVERT = "video_convert"
    VIDEO_TO_GIF = "video_to_gif"
    VIDEO_EXTRACT_FRAMES = "video_extract_frames"
    VIDEO_TRIM = "video_trim"
    GIF_SPLIT = "gif_split"
    GIF_MERGE = "gif_merge"

@dataclass
class Task:
    sources: list[Path]
    kind: TaskKind
    params: dict = field(default_factory=dict)
    output_mode: OutputMode = OutputMode.BESIDE
    unified_dir: Path | None = None
    outputs: list[Path] = field(default_factory=list)
    status: str = "pending"  # pending|running|done|failed|cancelled
    error: str | None = None

def _unique(path: Path, taken: set[Path]) -> Path:
    taken.add(path.resolve())
    if not path.exists() and path.resolve() not in taken - {path.resolve()}:
        return path
    n = 1
    while True:
        cand = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if not cand.exists() and cand.resolve() not in taken:
            taken.add(cand.resolve())
            return cand
        n += 1

def resolve_outputs(
    sources: list[Path],
    ext: str,
    output_mode: OutputMode,
    unified_dir: Path | None,
    op_subdir: str = "converted",
) -> list[Path]:
    ext = ext.lstrip(".").lower()
    taken: set[Path] = set()
    outs: list[Path] = []
    for src in sources:
        if output_mode is OutputMode.UNIFIED:
            if unified_dir is None:
                raise ValueError("unified_dir required for UNIFIED mode")
            base = unified_dir / f"{src.stem}.{ext}"
        else:
            base = src.parent / op_subdir / f"{src.stem}.{ext}"
        # never overwrite the source itself
        resolved_src = src.resolve()
        cand = base
        if cand.resolve() == resolved_src:
            cand = base.with_name(f"{base.stem} (0){base.suffix}")  # force unique loop
        outs.append(_unique_force(cand, taken, resolved_src))
    return outs

def _unique_force(path: Path, taken: set[Path], protected: Path | None) -> Path:
    n = 0
    while True:
        if n == 0:
            cand = path
        else:
            cand = path.with_name(f"{path.stem} ({n}){path.suffix}")
        ok = not cand.exists() and cand.resolve() not in taken
        if protected is not None and cand.resolve() == protected:
            ok = False
        if ok:
            taken.add(cand.resolve())
            return cand
        n += 1

# core/__init__.py
# (empty)

# main.py
from core.version import __version__

def main() -> None:
    from gui.main_window import run
    run(__version__)

if __name__ == "__main__":
    main()

# requirements.txt
PySide6>=6.7
Pillow>=10.3
pytest>=8.0
pyinstaller>=6.6
imageio-ffmpeg>=0.5
```

Fix `_unique` duplicate logic — final file uses only `_unique_force` (delete broken `_unique`).

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest -v`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: scaffold task model and output path resolution"
```

---

### Task 2: ffmpeg_finder

**Files:**
- Create: `core/ffmpeg_finder.py`, `tests/test_ffmpeg_finder.py`

**Interfaces:**
- Consumes: env `WALLPAPER_FORGE_FFMPEG`
- Produces: `class FFmpegNotFound(RuntimeError)`
- Produces: `find_ffmpeg() -> Path` — search order: `Path(sys.executable).parent` (and `parent/bin`) when frozen (`sys.frozen`), else repo `vendor/ffmpeg/ffmpeg.exe(.bat skip)` → env var → `PATH` (`shutil.which("ffmpeg")` / `ffmpeg.exe`) → `imageio_ffmpeg.get_ffmpeg_exe()` if importable; raise `FFmpegNotFound` with Chinese message if none
- Produces: `ffmpeg_available() -> bool` (no raise)

- [ ] **Step 1: Failing tests**

```python
# tests/test_ffmpeg_finder.py
import os
from pathlib import Path
from core.ffmpeg_finder import FFmpegNotFound, find_ffmpeg, ffmpeg_available

def test_env_var_wins(tmp_path, monkeypatch):
    fake = tmp_path / "ffmpeg.exe"
    fake.write_bytes(b"")
    monkeypatch.setenv("WALLPAPER_FORGE_FFMPEG", str(fake))
    monkeypatch.setattr("core.ffmpeg_finder.sys.frozen", False, raising=False)
    assert find_ffmpeg() == fake

def test_available_returns_bool():
    assert isinstance(ffmpeg_available(), bool)
```

- [ ] **Step 2: Run fail** — `pytest tests/test_ffmpeg_finder.py -v`

- [ ] **Step 3: Implement** `core/ffmpeg_finder.py`:

```python
from __future__ import annotations
import os, shutil, sys
from pathlib import Path

class FFmpegNotFound(RuntimeError):
    pass

def _candidates() -> list[Path]:
    found: list[Path] = []
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).parent
        found += [app_dir / "ffmpeg.exe", app_dir / "bin" / "ffmpeg.exe"]
    env = os.environ.get("WALLPAPER_FORGE_FFMPEG")
    if env:
        found.append(Path(env))
    here = Path(__file__).resolve().parent.parent
    found.append(here / "vendor" / "ffmpeg" / "ffmpeg.exe")
    which = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if which:
        found.append(Path(which))
    try:
        import imageio_ffmpeg
        found.append(Path(imageio_ffmpeg.get_ffmpeg_exe()))
    except Exception:
        pass
    return found

def find_ffmpeg() -> Path:
    for p in _candidates():
        if p and p.is_file():
            return p
    raise FFmpegNotFound(
        "未找到 ffmpeg。请安装 ffmpeg 并加入 PATH，或设置环境变量 WALLPAPER_FORGE_FFMPEG。"
    )

def ffmpeg_available() -> bool:
    try:
        find_ffmpeg()
        return True
    except FFmpegNotFound:
        return False
```

- [ ] **Step 4: Pass** — `pytest -v`
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: ffmpeg locator with layered search"`

---

### Task 3: image_ops + annotate (convert / resize / quality / crop / watermark)

**Files:**
- Create: `core/image_ops.py`, `core/annotate.py`, `tests/test_image_ops.py`, `tests/test_annotate.py`

**Interfaces:**
- Consumes: Pillow
- Produces: `convert_image(src: Path, dst: Path, *, max_width: int | None = None, quality: int = 90) -> Path` — opens with Pillow, applies optional proportional downscale to `max_width`, saves with format inferred from `dst.suffix`; quality only for JPG/WebP; creates parent dirs; returns `dst`
- Produces: `crop_image(src: Path, dst: Path, box: tuple[int, int, int, int]) -> Path` — box is `(left, top, right, bottom)` in source pixels; validates bounds
- Produces: `add_text_watermark(src, dst, *, text, font_size=32, color=(255,255,255,180), position="bottom_right", margin=16) -> Path` — position ∈ `top_left|top_right|bottom_left|bottom_right|center`
- Produces: `add_image_watermark(src, dst, *, mark: Path, scale=0.2, position="bottom_right", margin=16, opacity=0.8) -> Path`
- Produces: `class ImageOpError(Exception)` with Chinese messages

- [ ] **Step 1: Failing tests** (sample 64×48 PNG created in fixture)

```python
# tests/conftest.py
import pytest
from pathlib import Path
from PIL import Image

@pytest.fixture
def png_64(tmp_path: Path) -> Path:
    p = tmp_path / "img.png"
    Image.new("RGB", (64, 48), (10, 20, 30)).save(p)
    return p

@pytest.fixture
def gif_2f(tmp_path: Path) -> Path:
    p = tmp_path / "a.gif"
    frames = [Image.new("RGB", (16, 16), (i * 40, 0, 0)) for i in range(2)]
    frames[0].save(p, save_all=True, append_images=frames[1:], duration=100, loop=0)
    return p
```

```python
# tests/test_image_ops.py
from PIL import Image
from core.image_ops import convert_image, ImageOpError
import pytest

def test_png_to_jpg(png_64, tmp_path):
    out = convert_image(png_64, tmp_path / "o.jpg", quality=80)
    im = Image.open(out)
    assert im.format == "JPEG"
    assert im.size == (64, 48)

def test_max_width_downscale(png_64, tmp_path):
    out = convert_image(png_64, tmp_path / "o.png", max_width=32)
    assert Image.open(out).size == (32, 24)

def test_bad_suffix_raises(png_64, tmp_path):
    with pytest.raises(ImageOpError):
        convert_image(png_64, tmp_path / "o.xyz")
```

```python
# tests/test_annotate.py
from PIL import Image
from core.annotate import crop_image, add_text_watermark, add_image_watermark, ImageOpError
import pytest

def test_crop(png_64, tmp_path):
    out = crop_image(png_64, tmp_path / "c.png", (0, 0, 32, 24))
    assert Image.open(out).size == (32, 24)

def test_crop_out_of_bounds(png_64, tmp_path):
    with pytest.raises(ImageOpError):
        crop_image(png_64, tmp_path / "c.png", (0, 0, 999, 999))

def test_text_watermark(png_64, tmp_path):
    out = add_text_watermark(png_64, tmp_path / "w.png", text="测试")
    assert Image.open(out).size == (64, 48)

def test_image_watermark(png_64, tmp_path):
    mark = tmp_path / "m.png"
    Image.new("RGBA", (8, 8), (255, 0, 0, 200)).save(mark)
    out = add_image_watermark(png_64, tmp_path / "w2.png", mark=mark, scale=0.5)
    assert Image.open(out).size == (64, 48)
```

- [ ] **Step 2: Run fail**
- [ ] **Step 3: Implement** both modules (Pillow-only; load default font via `ImageFont.truetype("arial.ttf", size)` with fallback `ImageFont.load_default()`; watermark positions compute paste coordinates after alpha composite on RGBA copy; unsupported save suffix → `ImageOpError("不支持的输出格式: …")`)
- [ ] **Step 4: Pass** — `pytest -v`
- [ ] **Step 5: Commit** — `feat: image convert, crop, watermarks`

---

### Task 4: gif_ops (split / merge / video handled in Task 5)

**Files:**
- Create: `core/gif_ops.py`, `tests/test_gif_ops.py`

**Interfaces:**
- Produces: `split_gif(src: Path, out_dir: Path, *, step: int = 1) -> list[Path]` — writes `frame_0001.png`…; `step>=1` keeps every Nth frame; returns ordered paths
- Produces: `merge_gif(sources: list[Path], dst: Path, *, duration_ms: int = 100, loop: int = 0, reverse: bool = False) -> Path`
- Produces: `class GifOpError(Exception)`

- [ ] **Step 1: Failing tests**

```python
# tests/test_gif_ops.py
from pathlib import Path
from PIL import Image
from core.gif_ops import split_gif, merge_gif

def test_split_two_frames(gif_2f, tmp_path):
    frames = split_gif(gif_2f, tmp_path / "f")
    assert len(frames) == 2
    assert frames[0].name == "frame_0001.png"

def test_split_step(gif_2f, tmp_path):
    assert len(split_gif(gif_2f, tmp_path / "f", step=2)) == 1

def test_merge_roundtrip(gif_2f, tmp_path):
    frames = split_gif(gif_2f, tmp_path / "f")
    out = merge_gif(frames, tmp_path / "m.gif", duration_ms=50)
    im = Image.open(out)
    n = 0
    try:
        while True:
            im.seek(n); n += 1
    except EOFError:
        pass
    assert n == 2

def test_merge_reverse(gif_2f, tmp_path):
    frames = split_gif(gif_2f, tmp_path / "f")
    out = merge_gif(frames, tmp_path / "r.gif", reverse=True)
    assert out.exists()
```

- [ ] **Step 2: Fail → Step 3: Implement with Pillow `ImageSequence`/`save(save_all=True)` → Step 4: Pass → Step 5:** `feat: gif split and merge`

---

### Task 5: video_ops (convert / to_gif / extract_frames / trim)

**Files:**
- Create: `core/video_ops.py`, `tests/test_video_ops.py`, `tests/conftest.py` (extend with `tiny_mp4` fixture)

**Interfaces:**
- Consumes: `core.ffmpeg_finder.find_ffmpeg`
- Produces: `class VideoOpError(Exception)` — wraps Chinese messages; includes `stderr_tail` attr
- Produces: `run_ffmpeg(args: list[str], *, timeout: int = 600, cancel_event=None) -> None` — `subprocess.run([ffmpeg, "-y", "-hide_banner", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")`; if `cancel_event` is set during wait, kill process and raise `VideoOpError("已取消")`; non-zero → `VideoOpError` with last stderr lines
- Produces: `convert_video(src, dst, *, keep_audio: bool = True) -> Path` — map by suffix (`-c:v libx264 -c:a aac` for mp4/mov; `-c:v libvpx-vp9 -c:a libopus` for webm; mkv uses libx264/aac); no-audio adds `-an`
- Produces: `video_to_gif(src, dst, *, max_duration: float | None = None, fps: int = 15, width: int = 480) -> Path` — two-pass palette (`-vf "fps=…,scale=…:-1:flags=lanczos,split…palettegen…paletteuse"`) or single-pass `palettegen/use` filter; `-an`
- Produces: `extract_frames(src, out_dir, *, every_seconds: float | None = None, at_seconds: list[float] | None = None, ext: str = "png") -> list[Path]`
- Produces: `trim_video(src, dst, start: float, end: float) -> Path` — `-ss/-to` re-encode for accuracy

- [ ] **Step 1: Fixture + failing tests**

```python
# conftest addition
@pytest.fixture
def tiny_mp4(tmp_path: Path) -> Path:
    import subprocess
    from core.ffmpeg_finder import find_ffmpeg, FFmpegNotFound
    p = tmp_path / "tiny.mp4"
    try:
        ff = find_ffmpeg()
    except FFmpegNotFound:
        pytest.skip("ffmpeg not available")
    subprocess.run(
        [str(ff), "-y", "-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=1",
         "-pix_fmt", "yuv420p", str(p)],
        check=True, capture_output=True,
    )
    return p
```

```python
# tests/test_video_ops.py
from pathlib import Path
from core.video_ops import convert_video, video_to_gif, extract_frames, trim_video

def test_convert_to_webm(tiny_mp4, tmp_path):
    out = convert_video(tiny_mp4, tmp_path / "o.webm", keep_audio=False)
    assert out.exists() and out.stat().st_size > 0

def test_video_to_gif(tiny_mp4, tmp_path):
    out = video_to_gif(tiny_mp4, tmp_path / "o.gif", fps=5, width=32, max_duration=1)
    assert out.exists()

def test_extract_frames(tiny_mp4, tmp_path):
    outs = extract_frames(tiny_mp4, tmp_path / "fr", every_seconds=0.5)
    assert len(outs) >= 1 and outs[0].suffix == ".png"

def test_trim(tiny_mp4, tmp_path):
    out = trim_video(tiny_mp4, tmp_path / "t.mp4", 0, 0.4)
    assert out.exists()
```

- [ ] **Step 2: Fail** (skip if no ffmpeg — ensure `pip install imageio-ffmpeg` so finder succeeds)
- [ ] **Step 3: Implement** `core/video_ops.py` per interfaces above
- [ ] **Step 4: Pass** — `pytest -v`
- [ ] **Step 5: Commit** — `feat: ffmpeg video convert, gif, frames, trim`

---

### Task 6: GUI shell — main window, sidebar, four empty pages, settings persistence

**Files:**
- Create: `gui/__init__.py`, `gui/main_window.py`, `gui/styles.py`, `gui/pages/__init__.py`, `gui/pages/base.py`, `gui/pages/image_page.py`, `gui/pages/video_page.py`, `gui/pages/gif_page.py`, `gui/pages/settings_page.py`

**Interfaces:**
- Produces: `gui.main_window.run(version: str) -> None` — creates `QApplication`, applies dark stylesheet from `gui/styles.py`, shows `MainWindow`, `app.exec()`
- Produces: pages are `QWidget` subclasses with method `set_ffmpeg_ok(self, ok: bool) -> None`
- Settings JSON at `%APPDATA%/WallpaperConverter/settings.json`: keys `output_mode` (`beside`|`unified`), `unified_dir`, `default_quality` (int 90), `default_gif_fps` (int 15) — helpers in `gui/settings_store.py`: `load_settings() -> dict`, `save_settings(dict)`

- [ ] **Step 1:** Implement shell: left `QListWidget` (icons/text: 图片转换/视频转换/GIF 工具/设置), `QStackedWidget`, top status `QLabel`, dark QSS (background `#1e1e1e`, texts `#ddd`, accents `#3b82f6`)
- [ ] **Step 2:** Manual smoke: `python -c "from gui.main_window import run"` import check + `python -m compileall gui`
- [ ] **Step 3: Commit** — `feat: GUI shell with sidebar navigation`

---

### Task 7: BatchWorker + shared file-list widget + Image page wiring

**Files:**
- Create: `gui/workers.py`, `gui/widgets/file_table.py`, rewrite `gui/pages/image_page.py`
- Modify: `gui/main_window.py` (instantiate worker on start)

**Interfaces:**
- Produces: `class BatchWorker(QObject)` living in worker `QThread`:
  - signals: `progress(int, int, str)`, `task_finished(object)`, `batch_finished(int, int)` (ok, failed), `ffmpeg_missing(str)`
  - slots: `submit(list[Task])`, `cancel()`
  - executes Task kinds via `core.*`; on failure sets `task.status="failed"`, `task.error=映射中文`; never touches widgets
- Produces: `class FileTable(QWidget)` with `add_paths(list[Path])`, `selected_or_all() -> list[Path]`, `clear()`, `set_row_status(row, status, detail)`, signals `open_output_requested(Path)`
- Produces: Image page: drag-drop + add file/folder; format `QComboBox` PNG/JPG/WebP/BMP/GIF; optional `max_width` `QSpinBox` (0=off); quality slider 1–100; buttons 裁剪 / 水印 / 开始转换 / 取消 / 打开输出文件夹; output mode combo bound to settings

- [ ] **Step 1:** Implement `FileTable` + `BatchWorker` with image path only (other kinds: mark failed `"该功能尚未接入"` temporarily — removed as later tasks land)
- [ ] **Step 2:** Wire image page end-to-end; progress bar top of page
- [ ] **Step 3:** Smoke: import + compileall; run `pytest` still green
- [ ] **Step 4: Commit** — `feat: batch worker and image conversion page`

---

### Task 8: Crop & watermark dialogs

**Files:**
- Create: `gui/dialogs.py`

**Interfaces:**
- Produces: `class CropDialog(QDialog)` — shows image scaled to widget, rubber-band selection with mouse, outputs `box: tuple[int,int,int,int] | None`, `result` via `get_box() -> tuple | None` classmethod-style helper `CropDialog.get_box(parent, image_path)`
- Produces: `class WatermarkDialog(QDialog)` — tabs 文字水印 / 图片水印; returns dict `{"type": "text"|"image", ...params}` or `None`; `WatermarkDialog.get_params(parent, image_path) -> dict | None`
- Image page: 裁剪 runs `crop_image` then replaces row source with output (or adds output row); 水印 runs chosen watermark onto selection (batch: apply to all selected with same params, outputs beside-mode)

- [ ] **Step 1:** Implement dialogs + wire buttons
- [ ] **Step 2:** compileall + pytest
- [ ] **Step 3: Commit** — `feat: crop and watermark dialogs`

---

### Task 9: Video page + GIF page wiring

**Files:**
- Modify: `gui/pages/video_page.py`, `gui/pages/gif_page.py`

**Interfaces:**
- Video page modes (`QComboBox`): 格式互转 / 视频转 GIF / 截取帧 / 片段截取; dynamic param widget stacked below; start submits Tasks of kinds `VIDEO_CONVERT|VIDEO_TO_GIF|VIDEO_EXTRACT_FRAMES|VIDEO_TRIM`; if `not ffmpeg_available()` disable start + yellow banner
- GIF page modes: 拆帧 / 合帧; kinds `GIF_SPLIT|GIF_MERGE`; GIF split output to `converted/` subdir via `resolve_outputs` with ext `png` under `op_subdir=f"{stem}_frames"`; merge needs ordered multi-select
- Settings page: loads/saves `settings_store`; FFmpeg path label via `find_ffmpeg` or 未找到; 重新检测 button re-runs lookup and calls `set_ffmpeg_ok` on video page

- [ ] **Step 1:** Implement both pages + settings wiring
- [ ] **Step 2:** compileall + pytest
- [ ] **Step 3: Commit** — `feat: video, gif, and settings pages`

---

### Task 10: Vendor ffmpeg + packaging (PyInstaller + Inno Setup) + README

**Files:**
- Create: `vendor/ffmpeg/` (binary), `build/app.spec`, `build/installer.iss`, `README.md`, `LICENSE` (MIT)

**Steps:**
- [ ] **Step 1: Obtain ffmpeg.exe**

Try in order until one works:
1. `pip download imageio-ffmpeg -d vendor/_dl` then copy `imageio_ffmpeg` binary to `vendor/ffmpeg/ffmpeg.exe` (locate via `python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"` after `pip install imageio-ffmpeg`)
2. Fallback: download BtbN/gyan essentials zip and extract `bin/ffmpeg.exe`

Verify: `vendor\ffmpeg\ffmpeg.exe -version`

Note: `vendor/ffmpeg/*.exe` is large — commit it anyway for reproducible packaging (already allowed by `.gitignore` exception; adjust `.gitignore` so `vendor/ffmpeg/ffmpeg.exe` is **not** ignored — change `*.exe` rule to ignore only `dist/` and `build/` outputs).

- [ ] **Step 2: `build/app.spec`** — onedir, `name="WallpaperConverter"`, `main.py`, datas `[(vendor/ffmpeg/ffmpeg.exe, ".")]`, hiddenimports for `PIL._tkinter_finder` not needed; exclude unused Qt modules if trivial
- [ ] **Step 3: `pyinstaller build/app.spec --noconfirm`** → `dist/WallpaperConverter/WallpaperConverter.exe` exists; run exe with `--help`? App is GUI — at least check process starts and file present
- [ ] **Step 4: `build/installer.iss`** — AppId `{{8F3A2C1E-5B47-4D9A-9C21-WALLPAPERFORGE}`, AppName `WallpaperConverter`, AppVersion read manually from `core/version.py` (`0.1.0`), DefaultDirName `{pf}\WallpaperConverter`, Files: `dist\WallpaperConverter\*`, shortcuts, UninstallUnsilently; if Inno Setup compiler (`iscc`) missing on machine, still commit `.iss` and document build command in README
- [ ] **Step 5: README.md** (Chinese): 功能列表、开发运行 `pip install -r requirements.txt && python main.py`、测试 `pytest`、打包命令、Releases 下载说明、开源许可与 FFmpeg LGPL 说明
- [ ] **Step 6: Commit** — `chore: packaging scripts, vendored ffmpeg, readme`

---

### Task 11: GitHub publish + Release

**Files:** none (ops)

- [ ] **Step 1:** Ensure `gh auth status` works; if token invalid run interactive guidance: `gh auth refresh -h github.com` (user completes browser). If still broken, stop and tell user — do not invent tokens.
- [ ] **Step 2:** `gh repo create wallpaper-forge --public --source . --push --description "壁纸图片/视频批量格式转换工具（中文 GUI）"`
- [ ] **Step 3:** If Setup exe exists (`build/Output/WallpaperConverter-Setup-0.1.0.exe` or agreed path): `gh release create v0.1.0 "路径#WallpaperConverter-Setup-0.1.0.exe" --title "v0.1.0" --notes "首个版本：图片互转、视频互转、GIF 工具、裁剪水印"`
- [ ] **Step 4:** If Setup cannot be built on this machine (no Inno Setup): push repo, create Release with source tag and notes explaining installer build steps — report honestly to user.
- [ ] **Step 5: Final verify:** `git status` clean; `pytest -v` all green; report repo URL + release URL.

---

## Self-Review (plan author)

1. **Spec coverage:** 架构§3→Tasks1-2,6; 功能§4→Tasks3-5,7-9; 数据流§5→Task7; 错误§6→Tasks5,7; 测试§7→Tasks1-5; 打包§8→Task10; GitHub§9→Task11. Covered.
2. **Placeholders:** removed broken `_unique` note resolved by `_unique_force`; no TBDs.
3. **Type consistency:** `Task`, `TaskKind`, `OutputMode`, `resolve_outputs`, `find_ffmpeg`, `convert_image`, `split_gif`, `BatchWorker.submit` names stable across tasks.
