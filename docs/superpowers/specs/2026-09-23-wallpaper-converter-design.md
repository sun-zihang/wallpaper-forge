# Wallpaper Forge 设计文档

- 日期：2026-09-23
- 状态：已确认（四节设计均经用户逐节批准）
- 仓库名：`wallpaper-forge`（GitHub public，附 Release 安装包）

## 1. 背景与目标

为"已下载/已提取的壁纸"提供一个可打包分发的桌面应用，在通用图片与视频格式之间批量互转，并附带裁剪、水印、GIF 拆合帧等常用操作。经 GitHub 调研（RePKG、lianpkg、WallPaper-Converter、we_extracter、QFact.WE2Video 等），确认专有格式解包是另一类工具的职责；本项目明确做 **B→C 档：通用格式互转 + 附加编辑操作**，不处理 `.pkg`/`.tex`/`.mpkg` 专有格式。

**成功标准**

1. 干净 Windows 机器上运行 `setup.exe` 完成安装，无需自装 Python/FFmpeg
2. 图片互转、视频互转、视频转 GIF、GIF 拆帧/合帧、裁剪、水印均可完成
3. 批量转换有进度、可取消，单文件失败不中断批次
4. 源码公开在 GitHub `wallpaper-forge`，Releases 附安装包

## 2. 范围

### 2.1 功能范围

| 类别 | 能力 |
|------|------|
| 图片 | PNG / JPG / WebP / BMP / GIF（静态）互转；等比缩放；质量压缩 |
| 视频 | MP4 / WebM / MOV / MKV 互转；视频 → GIF；按时间点或每 N 秒截帧；片段截取；音频保留/去除 |
| GIF | 拆帧为 PNG 序列（可抽稀）；图片序列 → GIF（帧率/循环/倒放） |
| 编辑 | 矩形裁剪；文字水印与图片水印（缩放、透明度、九宫格位置） |
| 批量 | 拖拽/添加文件与文件夹；全选/反选；进度；取消；失败重试；打开输出目录 |

### 2.2 非目标

- 不解包 Wallpaper Engine 专有格式（`.pkg`/`.tex`/`.mpkg`）
- 不做壁纸下载、不调用 Steam
- 不做"一键设为 Windows 壁纸"
- 不做多语言（界面纯中文）
- 不测 GUI 自动化，仅测 `core`

## 3. 架构

三层，核心逻辑与界面分离：

```
wallpaper-forge/
├── core/                  # 纯 Python，不 import Qt
│   ├── image_ops.py       # 图片互转、缩放、质量
│   ├── video_ops.py       # 视频互转、截帧、片段（ffmpeg）
│   ├── gif_ops.py         # GIF 拆帧、合帧、视频转 GIF
│   ├── annotate.py        # 裁剪、水印
│   ├── ffmpeg_finder.py   # 定位 ffmpeg.exe
│   ├── tasks.py           # 任务模型与输出路径计算
│   └── version.py         # 单一版本号来源
├── gui/
│   ├── main_window.py     # 主窗口 + 侧边栏
│   ├── pages/             # 图片、视频、GIF、设置 四页
│   ├── workers.py         # BatchWorker（QThread）
│   └── dialogs.py         # 裁剪、水印、进度
├── assets/
├── build/
│   ├── app.spec           # PyInstaller
│   └── installer.iss      # Inno Setup
├── tests/
├── requirements.txt
└── main.py
```

**约定**

- `core` 只抛异常、返回结果；GUI 负责展示
- `ffmpeg_finder` 查找顺序：应用 exe 同目录 → `PATH` → 开发环境变量；找不到时视频/GIF 页置灰并提示，图片功能不受影响
- 输出路径统一由 `core/tasks.py` 计算：
  - 默认模式：`<源目录>/converted/<原名>.<新扩展名>`
  - 统一目录模式：用户选定文件夹，保持原文件名
  - 重名追加 `(1)`、`(2)` 后缀；永不覆盖源文件

## 4. 界面

主窗口：左侧竖排导航（图片转换 / 视频转换 / GIF 工具 / 设置），右侧内容区，顶栏全局状态与进度。纯中文。

1. **图片转换页**：导入列表（缩略图、尺寸、格式、状态）；输出格式选择；可选等比缩放宽度、质量滑条；裁剪/水印入口；输出模式与开始按钮。
2. **视频转换页**：格式互转；视频转 GIF（时长上限、帧率、宽度）；截帧（时间点 / 每 N 秒）；片段截取（起止时间）；音频保留/去除（转 GIF 强制去除）。
3. **GIF 工具页**：拆帧、合帧参数与动图预览。
4. **设置页**：输出模式默认值、默认质量/帧率、FFmpeg 路径显示与重新检测、关于与开源许可。

通用交互：转换中禁止重复开始；取消生效；完成后可打开输出文件夹；失败项保留原因并可重试。

## 5. 数据流与线程

```
导入 → 构造 Task（含输出路径，入队前解决重名）
     → BatchWorker 串行执行
     → 状态迁移时发信号（pending → running → done|failed|cancelled）
     → GUI 刷新列表与进度条
     → 汇总成功/失败；可重试失败项
```

| 线程 | 职责 | 禁止 |
|------|------|------|
| GUI 主线程 | 控件读写、信号槽 | 跑转换、等待子进程 |
| BatchWorker | 顺序执行 Task、调 `core` | 碰控件 |
| ffmpeg 子进程 | 实际转码 | — |

- 图片操作：Worker 内直接调用
- 视频操作：`subprocess.Popen`，Worker `poll()` 轮询；取消 = terminate 子进程 + 清空队列
- 单文件失败不中断批次

## 6. 错误处理

- 失败任务记录中文原因（映射表：不支持格式、FFmpeg 编码失败、磁盘空间不足等）
- ffmpeg 非零退出：抓 stderr 末尾归入原因
- 启动自检 ffmpeg；缺失仅影响视频/GIF 页
- `sys.excepthook` 写 `logs/last_error.log`，弹一次友好提示

## 7. 测试

- pytest，仅覆盖 `core`
- 夹具：微小 PNG、2 帧 GIF、1 秒 64×64 视频
- 断言：产物可被 Pillow/ffprobe 打开、重名规则、裁剪/水印不抛错、GIF 往返一致、ffmpeg 缺失时抛可识别异常

## 8. 打包与发布

1. PyInstaller onedir → `dist/WallpaperConverter/`（含 `ffmpeg.exe` 与许可文件）
2. Inno Setup → `WallpaperConverter-Setup-x.y.z.exe`
   - 默认 `C:\Program Files\WallpaperConverter`
   - 桌面 + 开始菜单快捷方式、卸载项
3. 版本号单一来源 `core/version.py`
4. 验收：干净 Windows 装包后四类功能各跑一遍

## 9. GitHub 交付

- public 仓库 `wallpaper-forge`；`gh repo create` + push
- `.gitignore`：`dist/`、`build/` 中间产物、`logs/`、`__pycache__/`、`*.spec.bak`
- README：中文简介、功能列表、开发运行方式、Releases 下载说明
- `gh release create v0.1.0` 附 Setup 安装包

## 10. 技术选型

| 项 | 选择 | 理由 |
|----|------|------|
| 语言 | Python 3.11+ | 出包链路成熟 |
| GUI | PySide6 | 控件丰富，适合批量列表/进度/拖拽 |
| 图片 | Pillow | 互转、裁剪、水印、GIF 全覆盖 |
| 视频 | 内置 ffmpeg.exe | 格式覆盖最稳，不依赖对方环境 |
| 打包 | PyInstaller + Inno Setup | 单 Setup 分发 |
| 分发 | GitHub public + Release | 用户已确认 |

## 11. 已确认的决策记录

- 范围：通用格式互转（非 WE 专有格式解包）
- 形态：GUI
- 能力档位：图片 + 视频 + 裁剪/水印/GIF 拆合帧
- 分发：Setup 安装包（非单文件绿色版）
- 界面语言：纯中文
- 输出：双模式，默认源旁 `converted` 子目录
- 完成后：推 GitHub，仓库 `wallpaper-forge`，public，发 Release
