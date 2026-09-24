# Wallpaper Converter

中文界面的壁纸图片/视频批量格式转换工具（Windows）。

## 功能

- **图片转换**：PNG / JPG / WebP / BMP / GIF 互转，可选等比缩放、质量压缩
- **裁剪**：鼠标框选区域裁剪
- **水印**：文字水印、图片水印（位置/缩放/透明度）
- **视频转换**：MP4 / WebM / MOV / MKV 互转，可保留或去除音频
- **视频转 GIF**：可设帧率、宽度、时长上限
- **截帧**：按每 N 秒导出图片序列
- **片段截取**：剪出循环壁纸片段
- **GIF 工具**：拆帧为 PNG 序列、图片序列合成为 GIF（帧率/循环/倒放）
- **批量**：拖拽添加、进度、取消、失败详情；一键「重试失败项」只重跑失败文件；完成对话框可直接打开输出文件夹，双击列表行定位到真实产物；「预览」/空格查看源图，GIF 播放动画；列表可按名称搜索、按类型/状态筛选、懒加载缩略图；全选/反选与「已选中 N/M」提示；输出默认到源文件旁 `converted/` 子目录，可切换统一目录；默认永不覆盖，勾选「覆盖已存在的输出」后允许覆盖已存在输出并复用输出目录（覆盖源前需确认）；快捷键：Ctrl+O 添加文件、Ctrl+Shift+O 添加文件夹、Ctrl+Enter 开始处理、Esc 取消任务、Ctrl+A 全选
- **记住现场**：窗口大小/位置、所在页签、上次输出格式与文件对话框目录自动保存（覆盖开关永不保存，每次启动默认关闭）
- **自动更新**：启动时静默检查 GitHub Release（可关），设置页可手动检查；安装包下载与 README 直链均优先国内镜像，失败回退官方源；下载完成后按 Release 资产摘要校验 SHA256，通过才启动安装
- **专有格式解包**：`.pkg` 解包、`.tex` 抽取内嵌 PNG/JPG/WebP/MP4、`.mpkg` 提取 MP4（纯 Python 实现，每个源文件输出到 `converted/<文件名>/`）
- **去水印**：图片框选区域内容修复（OpenCV inpaint）；视频框选区域整段 FFmpeg delogo 去除，输出 `*_clean` 文件
- **网页版**（[GitHub Pages](https://sun-zihang.github.io/wallpaper-forge/)，纯静态、文件不离开浏览器）：图片/GIF/视频/解包四页，支持拖拽投放、整批进度百分比、GIF 拆帧按 delta/disposal 正确合成、合帧编码提速约 47 倍且可随时取消

## 环境要求

- Windows 10/11
- FFmpeg（安装包已内置；开发模式下可通过 PATH、`WALLPAPER_FORGE_FFMPEG` 环境变量或 `vendor/ffmpeg/ffmpeg.exe` 提供）

## 开发运行

```bash
pip install -r requirements.txt
python main.py
```

## 测试

```bash
python -m pytest -v
```

覆盖 `core/` 纯逻辑（路径规则、图片/GIF/视频操作）与 `gui/` 的 offscreen 测试（设置持久化、覆盖确认、输出定位、全选/反选、失败重试、GIF 动画预览），网页版另有 82 个 Node 测试；GitHub Actions 在每次推送上跑桌面（Windows pytest）、网页（Ubuntu Node）与 CDN 钉版可达性三道检查，Pages 工作流自动部署网页版并联动 Live smoke 对线上站点巡检（每周亦定时执行）。

## 打包

```bash
# 1) PyInstaller（onedir，ffmpeg.exe 需在 vendor/ffmpeg/）
pyinstaller build/app.spec --noconfirm

# 2) Inno Setup 安装包（需安装 Inno Setup 6）
iscc build/installer.iss
```

产物：

- 程序目录：`dist/WallpaperConverter/`
- 安装包：`build/Output/WallpaperConverter-Setup-<版本>.exe`

也可以在 GitHub Actions 的 **Release build** 工作流（手动触发）一键完成以上两步，安装包在同一 run 的 Artifacts（`WallpaperConverter-Setup`）中下载；勾选 `create_draft_release` 还会顺带创建带安装包的草稿 Release。`core/version.py`、`build/installer.iss` 与本 README 的版本号由测试 `tests/test_release_meta.py` 保持一致。

## 下载

最新版：**[v0.6.3](https://github.com/sun-zihang/wallpaper-forge/releases/tag/v0.6.3)**（GIF 动画预览、磁盘空间预检；网页版已上线 GitHub Pages）

国内若 GitHub 较慢，优先用镜像直链（任选其一，粘贴到浏览器）：

| 来源 | 直链 |
|------|------|
| ghproxy.net | https://ghproxy.net/https://github.com/sun-zihang/wallpaper-forge/releases/download/v0.6.3/WallpaperConverter-Setup-0.6.3.exe |
| gh-proxy.com | https://gh-proxy.com/https://github.com/sun-zihang/wallpaper-forge/releases/download/v0.6.3/WallpaperConverter-Setup-0.6.3.exe |
| mirror.ghproxy.com | https://mirror.ghproxy.com/https://github.com/sun-zihang/wallpaper-forge/releases/download/v0.6.3/WallpaperConverter-Setup-0.6.3.exe |
| ghfast.top | https://ghfast.top/https://github.com/sun-zihang/wallpaper-forge/releases/download/v0.6.3/WallpaperConverter-Setup-0.6.3.exe |
| GitHub 官方 | https://github.com/sun-zihang/wallpaper-forge/releases/download/v0.6.3/WallpaperConverter-Setup-0.6.3.exe |

应用内「检查更新 → 立即更新」同样按上表顺序优先走镜像；全部失败时会在提示框里列出可复制的镜像链接。

校验下载完整性：每个 Release 均附 `SHA256SUMS.txt`，本地执行 `Get-FileHash .\WallpaperConverter-Setup-0.6.3.exe -Algorithm SHA256` 对比其中哈希即可。

发布页（含历史版本）：https://github.com/sun-zihang/wallpaper-forge/releases

## 许可

本仓库源码以 MIT 发布（见 `LICENSE`）。

二进制中包含：

- [Pillow](https://python-pillow.org/) — BSD-Clear
- [PySide6](https://doc.qt.io/qtforpython/) — LGPL-3.0
- [FFmpeg](https://ffmpeg.org/) — LGPL/GPL（本项目随包分发的构建应为 LGPL 兼容构建；如需重新编译请使用 LGPL 配置）
