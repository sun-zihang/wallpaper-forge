# 覆盖原文件（桌面版）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 桌面版各功能页增加「覆盖原文件」勾选：允许输出覆盖源文件与已存在输出，覆盖源前弹一次确认框；同路径写盘走 `.part` 临时文件原子替换。

**Architecture:** 路径解析在 `core/tasks.resolve_outputs` 与两处页面内路径函数上加 `overwrite` 开关；写入层用 `core/safeio.staged_dst` 在「dst==任一输入」时写 `<name>.part` 再 `os.replace`；`BasePage` 提供勾选框与 `_confirm_overwrite`，五个页面接线。worker/`Task.params` 零改动。

**Tech Stack:** Python 3.13、PySide6、Pillow、OpenCV、FFmpeg、pytest。

**Spec:** `docs/superpowers/specs/2026-09-23-wallpaper-overwrite-original-design.md`

## Global Constraints

- 仅桌面版；**不改** `web/`（工作区可能有与本计划无关的未提交 `web/` 改动——提交时只 `git add` 本任务列出的路径，严禁 `git add -A` / `git add .`）。
- 默认行为与现网一致：`overwrite` 默认 `False`；未勾选时绝不覆盖源、已存在输出仍追加 ` (n)`。
- 勾选框：`QCheckBox("覆盖原文件")`，属性名 `overwrite_check`，**不**写入 settings_store、不进 `apply_settings`。
- 确认框仅在「会覆盖**源文件**」时弹一次；标题 `确认覆盖`，正文 `将直接覆盖 {n} 个源文件，此操作不可恢复。\n继续？`，默认按钮 No；覆盖已有非源输出不弹。
- 临时文件：`dst.with_suffix(dst.suffix + ".part")`（例：`a.png` → `a.png.part`）；成功 `os.replace(part, dst)`；失败/取消删除 part。
- 批内去重保留：`overwrite=True` 时忽略磁盘 `exists()` 与 `protected`，但同批 `taken` 撞车仍加 ` (n)`。
- `Task` / `Task.params` **不**新增 `overwrite` 字段；`gui/workers.py` 不改。
- 每任务结束：全量 `python -m pytest -q` 必须全绿（基线 60 passed），再 commit。
- git 身份已有；push 需代理：`$env:HTTPS_PROXY=$env:HTTP_PROXY="http://127.0.0.1:7897"`。本计划任务只 commit，不 push（收尾统一 push）。

---

### Task 1: `resolve_outputs` overwrite 开关 + `would_overwrite_sources`

**Files:**
- Modify: `core/tasks.py`
- Test: `tests/test_tasks.py`

**Interfaces:**
- Consumes: 现有 `OutputMode`、`_unique_force`。
- Produces:
  - `resolve_outputs(sources, ext, output_mode, unified_dir, op_subdir="converted", *, overwrite: bool = False) -> list[Path]`
  - `would_overwrite_sources(sources, outputs) -> list[tuple[Path, Path]]`（仅 `resolve()` 相等的配对）

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_tasks.py`：

```python
from core.tasks import OutputMode, resolve_outputs, would_overwrite_sources


def test_overwrite_allows_same_path_as_source(tmp_path: Path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    outs = resolve_outputs(
        [src], "png", OutputMode.UNIFIED, tmp_path, overwrite=True
    )
    assert outs == [src]


def test_overwrite_keeps_existing_output_path(tmp_path: Path):
    src = tmp_path / "a.png"
    outdir = tmp_path / "out"
    outdir.mkdir()
    (outdir / "a.jpg").write_bytes(b"old")
    src.write_bytes(b"x")
    outs = resolve_outputs(
        [src], "jpg", OutputMode.UNIFIED, outdir, overwrite=True
    )
    assert outs == [outdir / "a.jpg"]


def test_overwrite_still_dedupes_within_batch(tmp_path: Path):
    a = tmp_path / "a.png"
    b = tmp_path / "sub" / "a.png"
    b.parent.mkdir()
    a.write_bytes(b"1")
    b.write_bytes(b"2")
    outs = resolve_outputs(
        [a, b], "jpg", OutputMode.UNIFIED, tmp_path / "out", overwrite=True
    )
    assert outs[0].name == "a.jpg"
    assert outs[1].name == "a (1).jpg"


def test_would_overwrite_sources_pairs(tmp_path: Path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    other = tmp_path / "converted" / "b.jpg"
    pairs = would_overwrite_sources([src, tmp_path / "b.png"], [src, other])
    assert pairs == [(src, src)]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_tasks.py -v`
Expected: FAIL（`would_overwrite_sources` ImportError 或 `overwrite` 未知参数）

- [ ] **Step 3: 实现**

`core/tasks.py` 中替换 `_unique_force` 与 `resolve_outputs`，并新增 `would_overwrite_sources`：

```python
def _unique_force(
    path: Path,
    taken: set[Path],
    protected: Path | None,
    *,
    overwrite: bool = False,
) -> Path:
    n = 0
    while True:
        if n == 0:
            cand = path
        else:
            cand = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if overwrite:
            ok = cand.resolve() not in taken
        else:
            ok = not cand.exists() and cand.resolve() not in taken
            if protected is not None and cand.resolve() == protected:
                ok = False
        if ok:
            taken.add(cand.resolve())
            return cand
        n += 1


def resolve_outputs(
    sources: list[Path],
    ext: str,
    output_mode: OutputMode,
    unified_dir: Path | None,
    op_subdir: str = "converted",
    *,
    overwrite: bool = False,
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
        outs.append(_unique_force(base, taken, src.resolve(), overwrite=overwrite))
    return outs


def would_overwrite_sources(
    sources: list[Path],
    outputs: list[Path],
) -> list[tuple[Path, Path]]:
    src_res = {s.resolve(): s for s in sources}
    pairs: list[tuple[Path, Path]] = []
    for o in outputs:
        key = o.resolve()
        if key in src_res:
            pairs.append((src_res[key], o))
    return pairs
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_tasks.py -v`
Expected: 全部 PASS（含原有 4 个）

- [ ] **Step 5: 全量回归**

Run: `python -m pytest -q`
Expected: 60+ passed

- [ ] **Step 6: Commit**

```bash
git add core/tasks.py tests/test_tasks.py
git commit -m "feat: resolve_outputs overwrite flag + would_overwrite_sources"
```

---

### Task 2: `core/safeio` + 图片写入同路径 temp+replace

**Files:**
- Create: `core/safeio.py`
- Modify: `core/image_ops.py`（`convert_image`）
- Modify: `core/annotate.py`（`crop_image`、`add_text_watermark`、`add_image_watermark`）
- Test: `tests/test_safeio.py`

**Interfaces:**
- Consumes: 无（纯 stdlib）。
- Produces:
  - `safeio.needs_part(src: Path, dst: Path) -> bool`
  - `safeio.part_path(dst: Path) -> Path`
  - `safeio.replace_part(part: Path, dst: Path) -> None`
  - `safeio.cleanup_part(part: Path) -> None`
  - `safeio.staged_dst(src: Path, dst: Path)` — 上下文管理器，yield 写入目标路径；退出时按需 replace / cleanup

- [ ] **Step 1: 写失败测试**

新建 `tests/test_safeio.py`：

```python
from pathlib import Path

from PIL import Image

from core.annotate import crop_image
from core.image_ops import convert_image
from core.safeio import cleanup_part, needs_part, part_path, replace_part, staged_dst


def test_part_path_appends_part(tmp_path: Path):
    assert part_path(tmp_path / "a.png") == tmp_path / "a.png.part"


def test_needs_part_same_and_different(tmp_path: Path):
    a = tmp_path / "a.png"
    a.write_bytes(b"x")
    b = tmp_path / "b.png"
    assert needs_part(a, a) is True
    assert needs_part(a, b) is False


def test_staged_dst_same_path_replaces(tmp_path: Path):
    src = tmp_path / "a.txt"
    src.write_bytes(b"old")
    with staged_dst(src, src) as target:
        assert target == part_path(src)
        target.write_bytes(b"new")
    assert src.read_bytes() == b"new"
    assert not part_path(src).exists()


def test_staged_dst_same_path_error_cleans_part(tmp_path: Path):
    src = tmp_path / "a.txt"
    src.write_bytes(b"old")
    try:
        with staged_dst(src, src) as target:
            target.write_bytes(b"half")
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert src.read_bytes() == b"old"
    assert not part_path(src).exists()


def test_staged_dst_different_path_direct(tmp_path: Path):
    src = tmp_path / "a.txt"
    dst = tmp_path / "b.txt"
    with staged_dst(src, dst) as target:
        assert target == dst
        target.write_bytes(b"x")
    assert dst.read_bytes() == b"x"


def test_convert_image_inplace(tmp_path: Path):
    src = tmp_path / "img.png"
    Image.new("RGB", (64, 48), (1, 2, 3)).save(src)
    out = convert_image(src, src, max_width=32)
    assert out == src
    assert Image.open(src).size == (32, 24)
    assert not part_path(src).exists()


def test_crop_inplace(tmp_path: Path):
    src = tmp_path / "img.png"
    Image.new("RGB", (64, 48), (9, 9, 9)).save(src)
    out = crop_image(src, src, (0, 0, 32, 24))
    assert out == src
    assert Image.open(src).size == (32, 24)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_safeio.py -v`
Expected: FAIL（`core.safeio` 不存在）

- [ ] **Step 3: 实现 `core/safeio.py`**

```python
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def part_path(dst: Path) -> Path:
    return dst.with_suffix(dst.suffix + ".part")


def needs_part(src: Path, dst: Path) -> bool:
    try:
        return dst.resolve() == src.resolve()
    except OSError:
        return False


def replace_part(part: Path, dst: Path) -> None:
    os.replace(part, dst)


def cleanup_part(part: Path) -> None:
    try:
        if part.is_file():
            part.unlink()
    except OSError:
        pass


@contextmanager
def staged_dst(src: Path, dst: Path) -> Iterator[Path]:
    """Yield the path to write. If same as src, write .part then replace on success."""
    if not needs_part(src, dst):
        yield dst
        return
    part = part_path(dst)
    try:
        yield part
    except BaseException:
        cleanup_part(part)
        raise
    else:
        replace_part(part, dst)
```

- [ ] **Step 4: 接线 `convert_image`**

`core/image_ops.py` 的 `convert_image` 保存段改为：

```python
from core.safeio import staged_dst
# ... 函数内原有校验/resize 之后：
    try:
        with staged_dst(src, dst) as target:
            im.save(target, **save_kw)
    except ImageOpError:
        raise
    except Exception as e:
        raise ImageOpError(f"保存失败: {dst.name}（{e}）") from e
    return dst
```

（模块顶部已有 `from PIL import Image`；在现有 import 区追加 `from core.safeio import staged_dst`。）

- [ ] **Step 5: 接线 `core/annotate.py` 三个写盘点**

`crop_image` 末尾：

```python
from core.safeio import staged_dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    with staged_dst(src, dst) as target:
        out.save(target)
    return dst
```

`add_text_watermark` 末尾：

```python
    with staged_dst(src, dst) as target:
        out.save(target)
    return dst
```

`add_image_watermark` 末尾：

```python
    with staged_dst(src, dst) as target:
        out.save(target)
    return dst
```

（三个函数都先 `dst.parent.mkdir(...)` 再进 `staged_dst`，保持原顺序。）

- [ ] **Step 6: 跑测试确认通过**

Run: `python -m pytest tests/test_safeio.py tests/test_image_ops.py -v`
Expected: 全部 PASS

- [ ] **Step 7: 全量回归**

Run: `python -m pytest -q`
Expected: 全绿（数量 ≥ 基线）

- [ ] **Step 8: Commit**

```bash
git add core/safeio.py core/image_ops.py core/annotate.py tests/test_safeio.py
git commit -m "feat: staged .part write for in-place image ops"
```

---

### Task 3: GIF 合帧与视频/去水印写入同路径安全

**Files:**
- Modify: `core/gif_ops.py`（`merge_gif`）
- Modify: `core/video_ops.py`（`convert_video`、`trim_video`）
- Modify: `core/rewatermark.py`（`inpaint_image`、`remove_video_watermark`）
- Test: `tests/test_gif_ops.py`、`tests/test_video_ops.py`、`tests/test_rewatermark.py`

**Interfaces:**
- Consumes: `core.safeio.{needs_part, part_path, replace_part, cleanup_part}`（Task 2）；`merge_gif` 因需对 `sources` 列表做 `any` 判断而不用 `staged_dst` 上下文管理器，直接用底层四函数。
- Produces: 同路径时行为与 Task 2 一致——写 `.part` 成功 replace、失败清理；ffmpeg 的 `cleanup=` 指向 part。

- [ ] **Step 1: 写失败测试**

`tests/test_gif_ops.py` 追加：

```python
from core.safeio import part_path


def test_merge_inplace_same_path(gif_2f, tmp_path):
    # 把源 GIF 也作为合并输入且输出路径相同（unified 指向源目录的场景）
    out_path = gif_2f  # a.gif
    frames = split_gif(gif_2f, tmp_path / "f")
    # 用 frames[0] 之外再塞一个同名目标：直接 merge 到 gif_2f
    out = merge_gif(frames + [gif_2f], out_path, duration_ms=50)
    assert out == gif_2f
    assert out.exists()
    assert not part_path(gif_2f).exists()
```

`tests/test_video_ops.py` 追加（沿用 `tiny_mp4` fixture，ffmpeg 缺失自动 skip）：

```python
from core.safeio import part_path


def test_convert_inplace_uses_part(tiny_mp4, tmp_path):
    import shutil

    src = tmp_path / "clip.mp4"
    shutil.copy(tiny_mp4, src)
    before = src.stat().st_size
    out = convert_video(src, src, keep_audio=False)
    assert out == src
    assert src.stat().st_size > 0
    assert not part_path(src).exists()
    assert before > 0


def test_trim_inplace_uses_part(tiny_mp4, tmp_path):
    import shutil

    src = tmp_path / "clip.mp4"
    shutil.copy(tiny_mp4, src)
    out = trim_video(src, src, 0, 0.4)
    assert out == src
    assert not part_path(src).exists()
```

`tests/test_rewatermark.py` 追加（图片 inpaint 不依赖 ffmpeg）：

```python
from pathlib import Path

from PIL import Image

from core.rewatermark import inpaint_image
from core.safeio import part_path


def test_inpaint_inplace(tmp_path: Path):
    src = tmp_path / "wm.png"
    Image.new("RGB", (32, 32), (200, 200, 200)).save(src)
    out = inpaint_image(src, src, [(2, 2, 10, 10)])
    assert out == src
    assert not part_path(src).exists()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_gif_ops.py::test_merge_inplace_same_path tests/test_rewatermark.py::test_inpaint_inplace -v`
Expected: FAIL（同路径直接写会出错或未走 part——`merge_inplace` 至少断言 `part_path` 不存在需实现后才稳；当前实现可能成功也可能不稳定，以 `staged_dst` 接线后稳定通过为准。`test_convert_inplace`/`test_trim_inplace` 在无 ffmpeg 时 skip。）

- [ ] **Step 3: 接线 `merge_gif`**

`core/gif_ops.py` 顶部 `from core.safeio import staged_dst`；保存段：

```python
    dst.parent.mkdir(parents=True, exist_ok=True)
    with staged_dst(sources[0], dst) as target:
        frames[0].save(
            target,
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=loop,
            optimize=False,
        )
    return dst
```

说明：`sources[0]` 只用于判断「输出是否落在某个输入上」——merge 的 `dst` 与**任一**输入同路径都会 needs_part 失败风险。为覆盖「dst 等于列表中任一 source」，改用显式判断：

```python
    from core.safeio import cleanup_part, needs_part, part_path, replace_part

    dst.parent.mkdir(parents=True, exist_ok=True)
    same = any(needs_part(p, dst) for p in sources)
    if not same:
        frames[0].save(
            dst, save_all=True, append_images=frames[1:],
            duration=duration_ms, loop=loop, optimize=False,
        )
        return dst
    part = part_path(dst)
    try:
        frames[0].save(
            part, save_all=True, append_images=frames[1:],
            duration=duration_ms, loop=loop, optimize=False,
        )
    except BaseException:
        cleanup_part(part)
        raise
    replace_part(part, dst)
    return dst
```

（此显式版本替代 `staged_dst`，因需对 `sources` 列表做 any 判断；模块级 import 写在文件顶部：`from core.safeio import cleanup_part, needs_part, part_path, replace_part`。）

- [ ] **Step 4: 接线 `convert_video` / `trim_video`**

`core/video_ops.py` 顶部：

```python
from core.safeio import cleanup_part, needs_part, part_path, replace_part
```

`convert_video` 中 `args.append(str(dst))` 与 `run_ffmpeg(..., cleanup=dst)` 改为：

```python
    same = needs_part(src, dst)
    target = part_path(dst) if same else dst
    args.append(str(target))
    run_ffmpeg(
        args,
        cancel_event=cancel_event,
        progress_cb=progress_cb,
        duration=probe_video_duration(src),
        cleanup=target,
    )
    if same:
        # run_ffmpeg 失败时已 cleanup；成功才 replace
        if not target.is_file():
            raise VideoOpError(f"输出为空: {dst.name}")
        replace_part(target, dst)
    return dst
```

`trim_video` 同样模式（`run_ffmpeg` 的 args 末项改为 `target`，`cleanup=target`，成功后 `if same: replace_part(target, dst)`）。

- [ ] **Step 5: 接线 `inpaint_image` / `remove_video_watermark`**

`core/rewatermark.py` 顶部：`from core.safeio import cleanup_part, needs_part, part_path, replace_part`。

`inpaint_image` 保存段：

```python
    dst.parent.mkdir(parents=True, exist_ok=True)
    same = needs_part(src, dst)
    target = part_path(dst) if same else dst
    if not cv2.imwrite(str(target), out):
        if same:
            cleanup_part(target)
        raise RewatermarkError(f"保存失败：{dst.name}")
    if same:
        replace_part(target, dst)
    return dst
```

`remove_video_watermark`：`args` 末项 `str(dst)` → `str(target)`；`run_ffmpeg(..., cleanup=target)`；成功校验 `target` 非空后 `if same: replace_part(target, dst)`；`same = needs_part(src, dst)`，`target = part_path(dst) if same else dst`。失败路径 `run_ffmpeg` 已 cleanup target，无需再处理。

- [ ] **Step 6: 跑测试确认通过**

Run: `python -m pytest tests/test_gif_ops.py tests/test_video_ops.py tests/test_rewatermark.py -v`
Expected: 全部 PASS（无 ffmpeg 时 video 两条 in-place 自动 skip，其余必过）

- [ ] **Step 7: 全量回归**

Run: `python -m pytest -q`
Expected: 全绿

- [ ] **Step 8: Commit**

```bash
git add core/gif_ops.py core/video_ops.py core/rewatermark.py tests/test_gif_ops.py tests/test_video_ops.py tests/test_rewatermark.py
git commit -m "feat: staged part write for gif/video/inpaint same-path outputs"
```

---

### Task 4: 解包/去水印路径函数 overwrite + `extract_tex` 同名替换

**Files:**
- Modify: `gui/pages/unpack_page.py`（`_out_dir_for`）
- Modify: `gui/pages/rewatermark_page.py`（`_clean_out`）
- Modify: `core/we_tex.py`（`extract_tex` 增加 `overwrite`）
- Modify: `gui/workers.py` 不改；`execute_task` UNPACK_TEX 调用处**不**改（`extract_tex` 默认 `overwrite=False` 时行为不变；解包整目录复用场景由页面传 out_dir，tex 单文件 extract 的 out_base 在复用目录内时需要 overwrite——见 Step 3 说明）
- Test: `tests/test_we_formats.py`（`extract_tex` overwrite）、GUI 路径函数用轻量 import 测试

**Interfaces:**
- Consumes: Task 1 的 overwrite 语义。
- Produces:
  - `_out_dir_for(src, mode, unified, *, overwrite: bool = False) -> Path`
  - `_clean_out(src, ext, mode, unified, *, overwrite: bool = False) -> Path`
  - `extract_tex(src, out_base, *, overwrite: bool = False) -> Path`

- [ ] **Step 1: 写失败测试**

`tests/test_we_formats.py` 追加：

```python
def test_extract_tex_overwrite_replaces_same_name(tmp_path: Path):
    # 构造内嵌 PNG 的 .tex（与现有 embedded 测试同布局）
    png_sig = b"\x89PNG\r\n\x1a\n" + b"\x00" * 10
    import struct as _struct

    blob = b"\x00" * 16 + _struct.pack("<I", len(png_sig)) + png_sig + b"\x00" * 8
    src = tmp_path / "scene.tex"
    src.write_bytes(blob)
    first = extract_tex(src, tmp_path / "out" / "scene")
    assert first.exists()
    # 默认再抽 → 不覆盖，带 (1)
    second = extract_tex(src, tmp_path / "out" / "scene")
    assert second != first and second.exists()
    # overwrite → 仍写第一个路径
    third = extract_tex(src, tmp_path / "out" / "scene", overwrite=True)
    assert third == first
```

新建 `tests/test_gui_paths.py`（只测纯函数，不起 QApplication）：

```python
from pathlib import Path

from core.tasks import OutputMode
from gui.pages.rewatermark_page import _clean_out
from gui.pages.unpack_page import _out_dir_for


def test_out_dir_for_overwrite_reuses_nonempty(tmp_path: Path):
    src = tmp_path / "scene.pkg"
    src.write_bytes(b"x")
    d = _out_dir_for(src, OutputMode.BESIDE, None, overwrite=False)
    d.mkdir(parents=True, exist_ok=True)
    (d / "old.bin").write_bytes(b"1")
    d2 = _out_dir_for(src, OutputMode.BESIDE, None, overwrite=True)
    assert d2 == d
    d3 = _out_dir_for(src, OutputMode.BESIDE, None, overwrite=False)
    assert d3.name.endswith("(1)")


def test_clean_out_overwrite_keeps_existing(tmp_path: Path):
    src = tmp_path / "a.png"
    src.write_bytes(b"x")
    out = _clean_out(src, "png", OutputMode.UNIFIED, tmp_path, overwrite=False)
    out.write_bytes(b"old")
    out2 = _clean_out(src, "png", OutputMode.UNIFIED, tmp_path, overwrite=True)
    assert out2 == out
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_gui_paths.py tests/test_we_formats.py -k overwrite -v`
Expected: FAIL（`overwrite` 参数不存在）

- [ ] **Step 3: 实现**

`core/we_tex.py` `extract_tex`：签名加 `*, overwrite: bool = False`；两处

```python
        n = 1
        while dst.exists():
            dst = out_base.with_name(f"{out_base.stem} ({n}){ext}")
            n += 1
```

改为：

```python
        if not overwrite:
            n = 1
            while dst.exists():
                dst = out_base.with_name(f"{out_base.stem} ({n}){ext}")
                n += 1
```

（`.tex` 回退分支同样处理。）

`gui/pages/unpack_page.py`：

```python
def _out_dir_for(
    src: Path, mode: OutputMode, unified: Path | None, *, overwrite: bool = False
) -> Path:
    stem = src.stem
    if mode is OutputMode.UNIFIED:
        assert unified is not None
        base = unified / stem
    else:
        base = src.parent / "converted" / stem
    if overwrite and base.exists() and base.is_dir():
        return base
    n = 1
    cand = base
    while True:
        conflict = cand.exists() and (not cand.is_dir() or any(cand.iterdir()))
        if not conflict:
            return cand
        cand = base.with_name(f"{stem} ({n})")
        n += 1
```

`gui/pages/rewatermark_page.py` `_clean_out`：签名加 `*, overwrite: bool = False`；函数体改为：

```python
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
```

**说明（UNPACK_TEX 调用链）：** `workers.execute_task` 里 `extract_tex(src, out_dir / src.stem)`——当 Task 4 Step 1 的 `_out_dir_for(overwrite=True)` 复用非空目录时，tex 默认 overwrite=False 仍会起 `scene (1).png`。为让「勾选后同名替换」贯穿，**允许本任务微改** `gui/workers.py` UNPACK_TEX 一行（这是唯一例外，且不是传 UI 勾选，而是：目录已由页面决定复用，extract 应覆盖同名）：

```python
        task.outputs = [extract_tex(src, out_dir / src.stem, overwrite=True)]
```

在 `overwrite=False` 的默认路径下，`_out_dir_for` 不会返回非空已有目录，传 `overwrite=True` 给 extract_tex 不改变默认行为（新目录里无同名冲突）。全量旧测试须仍绿——若有旧测试断言 extract_tex 在已有文件时改名，改回默认 `overwrite=False` 且仅当 `params` 场景需要时再传；**以 Step 6 结果为准：若 `test_extract_tex_*` 旧用例失败，则 workers 保持原调用，仅在测试里覆盖 overwrite 语义，页面复用目录时依赖 extract_pkg 已有的 write_bytes 覆盖。** 若失败，把 workers 行改回原样并在计划执行报告中记录。

- [ ] **Step 4: 跑新测试**

Run: `python -m pytest tests/test_gui_paths.py tests/test_we_formats.py -v`
Expected: 新用例 PASS；`extract_tex` 默认行为旧用例 PASS

- [ ] **Step 5: 全量回归**

Run: `python -m pytest -q`
Expected: 全绿

- [ ] **Step 6: Commit**

```bash
git add core/we_tex.py gui/pages/unpack_page.py gui/pages/rewatermark_page.py tests/test_gui_paths.py tests/test_we_formats.py
git add gui/workers.py  # 仅当 Step 3 说明中的 extract_tex(overwrite=True) 通过了 Step 5
git commit -m "feat: unpack/rewatermark path overwrite + extract_tex same-name replace"
```

---

### Task 5: BasePage 勾选框 + `_confirm_overwrite` + 五页接线 + README

**Files:**
- Modify: `gui/pages/base.py`
- Modify: `gui/pages/image_page.py`
- Modify: `gui/pages/gif_page.py`
- Modify: `gui/pages/video_page.py`
- Modify: `gui/pages/unpack_page.py`
- Modify: `gui/pages/rewatermark_page.py`
- Modify: `README.md`
- Test: `tests/test_gui_confirm.py`（纯逻辑层）

**Interfaces:**
- Consumes: Task 1 `would_overwrite_sources`；Task 4 的 `_out_dir_for` / `_clean_out` 的 `overwrite=`。
- Produces:
  - `BasePage.overwrite_check: QCheckBox`
  - `BasePage._confirm_overwrite(sources: list[Path], outs: list[Path]) -> bool`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_gui_confirm.py`：

```python
from pathlib import Path

from core.tasks import would_overwrite_sources


def test_confirm_logic_count_only_sources(tmp_path: Path):
    # _confirm_overwrite 的核心是 would_overwrite_sources；
    # 文案拼接 n = len(pairs)（与 base.py 实现一致）
    a = tmp_path / "a.png"
    a.write_bytes(b"x")
    existing = tmp_path / "converted" / "a.jpg"
    pairs = would_overwrite_sources([a], [a])
    assert len(pairs) == 1
    pairs2 = would_overwrite_sources([a], [existing])
    assert pairs2 == []
```

- [ ] **Step 2: 跑测试**

Run: `python -m pytest tests/test_gui_confirm.py -v`
Expected: PASS（Task 1 已提供函数；本测试锁住「确认只数源」语义）

- [ ] **Step 3: `gui/pages/base.py` 加勾选与确认**

import 区补 `QCheckBox`（已有 `QComboBox` 等，同文件顶部 PySide6.QtWidgets 列表加一项）。

`__init__` 中在 `self.output_mode` / `self.pick_out_btn` 创建之后、`bottom.addWidget(QLabel("输出："))` 之前准备好控件；在 `bottom.addWidget(self.unified_edit)` 之后插入：

```python
        self.overwrite_check = QCheckBox("覆盖原文件")
        self.overwrite_check.setToolTip("勾选后允许覆盖源文件与已存在的输出；覆盖源文件前会再确认一次")
        bottom.addWidget(self.overwrite_check)
```

文件末尾（或 `_submit` 附近）新增方法：

```python
    def _confirm_overwrite(self, sources: list[Path], outs: list[Path]) -> bool:
        from PySide6.QtWidgets import QMessageBox

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
```

（`apply_settings` **不要** touch `overwrite_check`。）

- [ ] **Step 4: 图片页接线**

`gui/pages/image_page.py`：

1. `start_batch` 中：
```python
        ow = self.overwrite_check.isChecked()
        outs = resolve_outputs(paths, ext, mode, self.unified_dir, overwrite=ow)
        if not self._confirm_overwrite(paths, outs):
            return
```
（放在 `outs = ...` 之后、`task = Task(...)` 之前。）

2. `_crop` 中 `outs = resolve_outputs(..., overwrite=self.overwrite_check.isChecked())`，随后 `if not self._confirm_overwrite([src], outs): return`。

3. `_watermark` 中同样：`resolve_outputs(..., overwrite=...)`，`if not self._confirm_overwrite(paths, outs): return`。

- [ ] **Step 5: GIF 页接线**

`gui/pages/gif_page.py` 合帧分支：

```python
            outs = resolve_outputs(
                [base_src], ".gif", out_mode, self.unified_dir,
                overwrite=self.overwrite_check.isChecked(),
            )
            if not self._confirm_overwrite(imgs, outs):
                return
```

（`_confirm_overwrite` 的 sources 用合并输入全表 `imgs`——只有 `base_src` 会成为输出路径的源。拆帧分支写目录，不调 resolve/confirm。）

- [ ] **Step 6: 视频页接线**

`gui/pages/video_page.py` 三处 resolve：

```python
ow = self.overwrite_check.isChecked()
outs = resolve_outputs(paths, ext, out_mode, self.unified_dir, overwrite=ow)   # convert
# gif:
outs = resolve_outputs(paths, ".gif", out_mode, self.unified_dir, overwrite=ow)
# trim:
outs = resolve_outputs(paths, ".mp4", out_mode, self.unified_dir, overwrite=ow)
```

每处在构造 `Task` 前：

```python
if not self._confirm_overwrite(paths, outs):
    return
```

frames 分支目录不经 resolve，不 confirm。

- [ ] **Step 7: 解包页接线**

`gui/pages/unpack_page.py` `start_batch` 循环改为先收集再确认：

```python
        ow = self.overwrite_check.isChecked()
        batch: list[Task] = []
        out_dirs: list[Path] = []
        for p in paths:
            kind = _KIND_BY_EXT[p.suffix.lower()]
            out_dir = _out_dir_for(p, mode, self.unified_dir, overwrite=ow)
            out_dirs.append(out_dir)
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
        if not self._confirm_overwrite(paths, out_dirs):
            return
        self._submit(batch)
```

- [ ] **Step 8: 去水印页接线**

`gui/pages/rewatermark_page.py` 循环内两处 `_clean_out(p, ..., overwrite=self.overwrite_check.isChecked())`；循环后：

```python
        outs = [t.outputs[0] for t in batch]
        if not self._confirm_overwrite(paths, outs):
            return
        self._submit(batch)
```

- [ ] **Step 9: README**

`README.md` 第 15 行「永不覆盖原文件」改为：

```
- **批量**：拖拽添加、进度、取消、失败详情；输出默认到源文件旁 `converted/` 子目录，可切换统一目录；默认永不覆盖，勾选「覆盖原文件」后允许就地覆盖源文件与已存在输出（覆盖源前需确认）
```

- [ ] **Step 10: 跑测试**

Run: `python -m pytest tests/test_gui_confirm.py tests/test_gui_paths.py -v`
Expected: PASS

- [ ] **Step 11: 全量回归**

Run: `python -m pytest -q`
Expected: 全绿

- [ ] **Step 12: 手动冒烟（有显示环境时）**

`python main.py`：确认底栏出现「覆盖原文件」；勾选 + 统一目录指到源文件夹 + 同格式转换 → 出现确认框，取消不跑、确认后源文件被就地替换且无 `.part` 残留；不勾选行为与旧版一致。

- [ ] **Step 13: Commit**

```bash
git add gui/pages/base.py gui/pages/image_page.py gui/pages/gif_page.py gui/pages/video_page.py gui/pages/unpack_page.py gui/pages/rewatermark_page.py tests/test_gui_confirm.py README.md
git commit -m "feat: overwrite-original checkbox with source-confirm on all pages"
```

---

## 收尾（计划执行完后由 controller 做，不在单任务内）

- [ ] `python -m pytest -q` 全绿
- [ ] 统一 push：`$env:HTTPS_PROXY=$env:HTTP_PROXY="http://127.0.0.1:7897"; git push origin main`
- [ ] 确认 `git status` 未把无关 `web/` 改动带进提交
