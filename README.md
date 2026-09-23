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
- **批量**：拖拽添加、进度、取消、失败详情；输出默认到源文件旁 `converted/` 子目录，可切换统一目录；永不覆盖原文件
- **自动更新**：启动时静默检查 GitHub Release（可关），设置页可手动检查；安装包下载走镜像加速，失败回退官方源

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

仅覆盖 `core/` 纯逻辑（路径规则、图片/GIF/视频操作）。

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

## 下载

请到 GitHub **Releases** 页面下载最新 `WallpaperConverter-Setup-*.exe`。

## 许可

本仓库源码以 MIT 发布（见 `LICENSE`）。

二进制中包含：

- [Pillow](https://python-pillow.org/) — BSD-Clear
- [PySide6](https://doc.qt.io/qtforpython/) — LGPL-3.0
- [FFmpeg](https://ffmpeg.org/) — LGPL/GPL（本项目随包分发的构建应为 LGPL 兼容构建；如需重新编译请使用 LGPL 配置）
