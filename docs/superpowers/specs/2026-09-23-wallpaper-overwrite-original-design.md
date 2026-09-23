# 覆盖原文件（桌面版）设计

- 日期：2026-09-23
- 状态：已与用户确认，待实现
- 范围：仅桌面版（PySide6）；网页版不改

## 背景与目标

当前桌面版**永不覆盖**：输出固定进源旁 `converted/` 子目录或统一目录，`core/tasks.resolve_outputs` 用 `_unique_force` 把源路径当保护区，磁盘已存在则自动追加 ` (n)`；README 亦写明「永不覆盖原文件」。

用户需要一个可选开关「覆盖原文件」，勾选后：

1. 允许输出路径等于源文件（同格式就地覆盖，如原地压缩/缩小）；
2. 允许覆盖磁盘上已存在的输出（含上次输出），不再追加 ` (n)`。

已确认的约束：

| 决策点 | 结论 |
| --- | --- |
| 范围 | 仅桌面版 |
| 覆盖对象 | 源文件本身 + 已存在输出（两者都要） |
| 功能页 | 全部功能页（图片、GIF、视频、解包、去水印） |
| 默认与记忆 | 勾选默认关，**不写入** settings_store，每次启动为关 |
| 安全闸 | 勾选后点开始，若本次会覆盖**源文件**，弹一次确认框（列出受影响文件数）；覆盖非源的已有输出不弹框 |

## 方案取舍

- **采用 A：路径解析层加 `overwrite` 开关**——三处路径纯函数 + UI 勾选 + 同路径 temp+replace；`core/` 不碰 Qt，可测性好。
- 否 B（转换完事后再改名覆盖）：两阶段失败留半成品/丢文件，视频长任务风险窗口大。
- 否 C（设置页全局记忆）：与「默认关、不记忆」冲突。

## 架构与组件

### 1. 核心路径规则（`core/tasks.py`）

- `resolve_outputs(sources, ext, output_mode, unified_dir, op_subdir="converted", *, overwrite: bool = False) -> list[Path]`
- `_unique_force(path, taken, protected, *, overwrite: bool = False)`：
  - `overwrite=False`：行为与现状完全一致（查 `exists()`、拒绝 `protected`、批内 `taken`）。
  - `overwrite=True`：**不**因磁盘已存在而改名，**不**把 `protected`（源）当拒绝条件（允许 `cand == protected`）；批内 `taken` 去重**仍生效**——同一批两个源算出同一输出时，后者仍加 ` (n)`，避免批内互踩。
- 新增纯函数 `would_overwrite_sources(sources: Sequence[Path], outputs: Sequence[Path]) -> list[tuple[Path, Path]]`：按 `resolve()` 逐对比较，返回 `output == source` 的配对；供 UI 计算确认框中的受影响文件数。
- `Task` 不新增字段、**不**塞 `params["overwrite"]`：写入层只看「`dst.resolve()` 是否等于输入路径」自判是否走 temp+replace，与 UI 勾选解耦（勾选只影响路径解析结果）。

### 2. 同路径写盘安全（`core/` 写入层）

- **强制 temp+replace（不可省）**：凡最终 `dst.resolve()` 等于某输入文件的路径——先写同目录临时文件（`dst.with_suffix(dst.suffix + ".part")`），成功后 `os.replace(tmp, dst)`；失败/取消删除 tmp，不留半成品（对齐 0.5.0「取消删除输出」约定）。
- **覆盖已存在的非源输出**：允许直接覆盖写（不强制 temp）；实现若统一走 temp 也可，但不得改变 `overwrite=False` 的既有行为与测试预期。
- **图片**（`convert_image`、裁剪、水印 `annotate`）：就地时 save 到 tmp 再 replace，避免 Pillow 持有源文件句柄时直接覆盖。
- **视频/GIF**（ffmpeg）：**输入输出绝不允许同路径喂给 ffmpeg**——input 恒为源，output 恒为 tmp，成功后 replace。取消/非零退出删除 tmp。
- 临时文件命名固定为 `<最终名>.part`（同目录），不引入 `.tmp-<pid>` 变体，便于测试断言无残留。

### 3. 解包（`gui/pages/unpack_page._out_dir_for` + `core/we_*`）

- `_out_dir_for(..., *, overwrite: bool = False)`：`overwrite=True` 时若 `base` 已存在且是目录，直接返回 `base`（不再因非空而起 `stem (n)`）。
- 解包写入对该目录内**同名文件**允许覆盖写（`extract_pkg` 等内部若另有 unique 逻辑，以「overwrite 时同名替换」为准）。
- 解包源是 `.pkg/.tex/.mpkg`，输出是目录/内嵌文件，通常不会与源同路径；若出现同路径（如解出同名文件）走 §2 tmp+replace。

### 4. 去水印（`gui/pages/rewatermark_page._clean_out`）

- `_clean_out(..., *, overwrite: bool = False)`：`overwrite=True` 时跳过「`base.exists()` 就加 ` (n)`」两段循环；仅当 `base.resolve() == src.resolve()` **且** 不允许覆盖源时才退到 `_out` 后缀——勾选覆盖时允许 `base == src`（用户明确要就地）。
- `rewatermark.py` 实际写盘按 §2 处理同路径。

### 5. UI（`gui/pages/base.py`）

- 底栏「输出：」下拉旁增加 `QCheckBox("覆盖原文件")`，属性名 `self.overwrite_check`；默认不勾；**不**进 `apply_settings` / settings_store。
- `BasePage` 新增辅助方法 `_confirm_overwrite(sources: list[Path], outs: list[Path]) -> bool`：未勾选返回 `True`；勾选且 `would_overwrite_sources(sources, outs)` 非空时弹
  `QMessageBox.question(self, "确认覆盖", f"将直接覆盖 {n} 个源文件，此操作不可恢复。\n继续？", Yes|No, No)`，按用户选择返回；勾选但无源覆盖返回 `True`（不弹框）。
- **调用点唯一约定**：各页 `start_batch` 在算完 `outs`/`out_dirs`（尚未 `_submit`）时调用 `_confirm_overwrite(page_sources, page_outs)`，返回 `False` 则 `return` 不提交。不依赖 `Task.outputs`（该字段仍是 worker 跑完才回填）。
- 确认框只看**源**；覆盖已有非源输出不弹。

### 6. 各页接线

每页 `start_batch` 统一做两件事：① `resolve` 时传 `overwrite=self.overwrite_check.isChecked()`（路径层生效，不进 `Task.params`）；② `_submit` 前调 `_confirm_overwrite(...)`。

| 页面 | 改动 |
| --- | --- |
| 图片 `image_page.py` | 三处 `resolve_outputs(..., overwrite=...)`；裁剪/水印入口同样读勾选并 `_confirm_overwrite` |
| GIF `gif_page.py` | 合帧 `resolve_outputs(..., overwrite=...)` + `_confirm_overwrite`（拆帧写目录内文件，已天然覆盖同名帧，无需改路径算法） |
| 视频 `video_page.py` | convert/gif/trim 三处 `resolve_outputs(..., overwrite=...)` + `_confirm_overwrite`（frames 目录同拆帧） |
| 解包 `unpack_page.py` | `_out_dir_for(..., overwrite=...)` + `_confirm_overwrite(paths, out_dirs)` |
| 去水印 `rewatermark_page.py` | `_clean_out(..., overwrite=...)` + `_confirm_overwrite` |
| worker `gui/workers.py` | **零改动**：路径已在页面算好；写入层按「dst 是否等于输入」自选 temp+replace |

### 7. 错误处理

- 覆盖写失败（文件占用/权限）：保留源与旧输出，任务状态「失败」+ 原因（现有 `ImageOpError` / `VideoOpError` / `friendlyError` 链路）。
- 取消发生在 tmp 写入中：删 tmp；源保持完整。
- 就地覆盖中途进程被杀：可能留下 `*.part` 残留，不在本设计内做启动清扫（可作后续优化）。

### 8. 测试

- `tests/test_tasks.py`：
  - `overwrite=True` 时 `dst == src`（unified 且 `unified_dir == src.parent`、同 ext）返回源路径；
  - `overwrite=True` 时已存在输出路径被原样返回（不加 ` (n)`）；
  - 批内两源同输出仍去重；
  - `overwrite=False` 回归现状；
  - `would_overwrite_sources` 命中/不命中。
- `tests/test_image_ops.py`（及 gif/video 对应用例）：同路径写成功且内容更新；失败/取消时源完好、无 `.part` 残留。
- 解包：非空输出目录在 overwrite 下复用并覆盖同名文件。
- 去水印：已有 `_clean` 被覆盖；勾选且 base==src 时就地写。
- GUI 确认框不做自动化（现有测试无 GUI 框架）；逻辑经 `would_overwrite_sources` 单测覆盖。
- 全量 `python -m pytest -q` 保持既有 60+ 用例全绿，新增用例另行通过。

### 9. 文档

- README 批量一节：「永不覆盖原文件」改为「默认永不覆盖；勾选『覆盖原文件』后允许就地覆盖源文件与已存在输出（覆盖源前需确认）」。
- 桌面 spec（`2026-09-23-wallpaper-converter-design.md`）不回改；本 spec 为增量约定。

## 明确不做

- 不记忆勾选、不加全局设置项。
- 网页版不改。
- 不做覆盖前逐文件备份。
- 不做启动时清扫历史 `*.part` 残留（记为后续可选）。

## 验收清单

- [ ] 默认（未勾选）行为与现网完全一致，`resolve_outputs` 旧测试全绿。
- [ ] 勾选后：同格式同目录转换可 `dst == src` 就地成功；源内容被新结果替换。
- [ ] 勾选后：已存在输出被覆盖，无 ` (1)`。
- [ ] 勾选且会覆盖源时，开始前出现一次确认框，取消则不提交。
- [ ] 批内同名输出仍去重。
- [ ] 解包勾选后复用非空目录；去水印勾选后覆盖已有 `_clean`。
- [ ] 同路径写失败/取消：源完好，无 `.part` 残留。
- [ ] `python -m pytest -q` 全绿；README 已更新。
