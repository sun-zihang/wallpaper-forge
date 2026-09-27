# 视频编辑功能设计

## 概述

为 wallpaper-forge 项目添加完整的视频编辑功能，支持网页版和桌面版，采用时间线交互模式。

## 需求

### 功能范围
- 多段合并/拼接
- 速度调整（慢放/快放）
- 画面调整（旋转/翻转/裁剪/缩放）
- 音频处理（提取/替换/添加/音量/淡入淡出）
- 叠加内容（文字标题/图片水印）
- 滤镜/调色（亮度/对比度/饱和度/色相/灰度/怀旧/模糊/锐化）

### 平台
- 网页版（基于 FFmpeg WASM）
- 桌面版（基于本地 FFmpeg）

### 场景
- 壁纸制作（循环片段裁剪、拼接）
- 通用视频编辑

### UI 交互
- 时间线模式
- 多轨道（视频轨 + 音频轨 + 叠加轨）

### 导出
- 高级导出（编码器选择、码率控制、音频编码）
- 格式：MP4 / WebM

## 架构

### 整体架构

采用"核心引擎 + 双平台 UI"架构：

```
┌─────────────────────────────────────────────────────────────┐
│                      共享核心层 (纯 JS)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ 时间线数据模型 │  │ 编辑操作引擎  │  │ 预览帧计算器      │  │
│  │ TimelineModel │  │ EditEngine   │  │ PreviewCalculator│  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ 片段参数系统  │  │ 滤镜/效果管线 │  │ 导出任务编排器    │  │
│  │ ClipParams   │  │ FilterPipeline│  │ ExportOrchestrator│ │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼                               ▼
┌─────────────────────────┐    ┌─────────────────────────┐
│      网页版 UI           │    │      桌面版 UI           │
│  ┌───────────────────┐  │    │  ┌───────────────────┐  │
│  │ Canvas 预览渲染    │  │    │  │ Qt/QML 预览渲染    │  │
│  └───────────────────┘  │    │  └───────────────────┘  │
│  ┌───────────────────┐  │    │  ┌───────────────────┐  │
│  │ FFmpeg WASM 导出   │  │    │  │ 本地 FFmpeg 导出    │  │
│  └───────────────────┘  │    │  └───────────────────┘  │
└─────────────────────────┘    └─────────────────────────┘
```

### 模块职责

| 模块 | 职责 | 平台 |
|------|------|------|
| `TimelineModel` | 时间线数据结构、片段/轨道管理、序列化 | 共享 |
| `EditEngine` | 编辑操作：split/trim/reorder/duplicate，撤销重做 | 共享 |
| `ClipParams` | 片段参数：速度、画面变换、音频、叠加、滤镜 | 共享 |
| `PreviewCalculator` | 根据时间线和参数计算任意时间点的预览帧 | 共享 |
| `FilterPipeline` | FFmpeg filter 图生成、参数校验 | 共享 |
| `ExportOrchestrator` | 导出任务编排、进度报告、错误处理 | 共享 |
| `WebPreviewRenderer` | Canvas/WebCodecs 实时预览 | 网页 |
| `QtPreviewRenderer` | QML/QPainter 实时预览 | 桌面 |
| `FFmpegWasmExporter` | 调用 FFmpeg WASM 导出 | 网页 |
| `FFmpegNativeExporter` | 调用本地 FFmpeg 导出 | 桌面 |

### 数据流

```
用户操作 → EditEngine → TimelineModel → PreviewCalculator → 预览渲染
                                    ↓
                              ExportOrchestrator → FFmpeg 导出
```

## 核心数据模型

### 数据结构

```javascript
// 时间线模型
{
  id: string,
  name: string,
  duration: number,           // 总时长（秒），由所有片段计算得出
  tracks: Track[],
  audioSampleRate: 48000,
  audioChannels: 2,
  createdAt: ISOString,
  modifiedAt: ISOString,
}

// 轨道
{
  id: string,
  type: 'video' | 'audio' | 'overlay',
  name: string,
  clips: Clip[],
  muted: boolean,
  locked: boolean,
  visible: boolean,           // 仅 overlay 轨有效
}

// 片段
{
  id: string,
  sourceFile: string,         // 源文件名（虚拟 FS 路径）
  timelineIn: number,         // 在时间线上的起始位置（秒）
  sourceIn: number,           // 源文件截取起始（秒）
  sourceOut: number,          // 源文件截取结束（秒）
  speed: 1.0,                 // 播放速度
  params: {
    transform: {              // 画面变换
      rotation: 0,            // 0 | 90 | 180 | 270
      flipH: false,
      flipV: false,
      scale: 1.0,             // 缩放比例
      crop: null | { x, y, width, height },  // 裁剪区域（像素）
    },
    audio: {
      volume: 1.0,            // 音量倍率
      fadeIn: 0,              // 淡入时长（秒）
      fadeOut: 0,             // 淡出时长（秒）
      detune: 0,              // 音调调整（半音）
    },
    overlay: null | {         // 文字/图片叠加
      type: 'text' | 'image',
      text: string,
      fontFamily: string,
      fontSize: number,
      fontColor: string,
      position: { x, y },     // 百分比
      opacity: 1.0,
      imageFile: string,      // type=image 时有效
      scale: 1.0,
    },
    filters: {                // 调色滤镜
      brightness: 0,          // -1.0 ~ 1.0
      contrast: 0,            // -1.0 ~ 1.0
      saturation: 0,          // -1.0 ~ 1.0
      hue: 0,                 // -180 ~ 180 度
      grayscale: false,
      sepia: false,
      blur: 0,                // 模糊半径
      sharpen: 0,             // 锐化强度
    },
  },
  get duration() { return (this.sourceOut - this.sourceIn) / this.speed; }
}
```

### 时间线约束

- 同一轨道内片段不可重叠（UI 层保证，引擎层校验）
- 片段最小长度 0.1 秒
- `timelineIn` 始终 >= 0
- `sourceOut > sourceIn`
- `speed` 范围 0.1 ~ 10.0

### 编辑操作（EditEngine）

| 操作 | 说明 |
|------|------|
| `split(clipId, time)` | 在 time 处拆分片段 |
| `trim(clipId, newIn, newOut)` | 调整片段边界 |
| `move(clipId, newTrackId, newIn)` | 移动片段 |
| `remove(clipId)` | 删除片段 |
| `duplicate(clipId)` | 复制片段 |
| `reorder(trackId, clipIds)` | 重新排序 |
| `adjustSpeed(clipId, speed)` | 调整速度 |
| `adjustParams(clipId, partialParams)` | 更新参数 |

### 撤销/重做

- 命令模式：每个操作封装为 `{ undo(), redo() }`
- 栈深度 50
- `undo()` / `redo()` 直接操作 `TimelineModel`

### 序列化格式

```json
{
  "version": 1,
  "timeline": { },
  "exportSettings": {
    "format": "mp4",
    "videoCodec": "libx264",
    "audioCodec": "aac",
    "crf": 23,
    "preset": "veryfast",
    "resolution": "source"
  }
}
```

## 编辑引擎

采用命令模式，所有编辑操作封装为命令对象：

```javascript
class EditEngine {
  constructor(timeline) {
    this.timeline = timeline;
    this.undoStack = [];
    this.redoStack = [];
  }

  execute(command) {
    command.redo(this.timeline);
    this.undoStack.push(command);
    this.redoStack = [];
    if (this.undoStack.length > 50) this.undoStack.shift();
  }

  undo() {
    const cmd = this.undoStack.pop();
    if (!cmd) return false;
    cmd.undo(this.timeline);
    this.redoStack.push(cmd);
    return true;
  }

  redo() {
    const cmd = this.redoStack.pop();
    if (!cmd) return false;
    cmd.redo(this.timeline);
    this.undoStack.push(cmd);
    return true;
  }
}
```

## 预览计算

### PreviewCalculator

给定时间线状态 + 时间点 `t`，计算出该时刻的预览帧描述：

- 找到所有轨道上覆盖时间 t 的片段
- 对每个片段计算源时间：`sourceTime = clip.sourceIn + (t - clip.timelineIn) * clip.speed`
- 分离图层类型：视频层、音频层、叠加层
- 音频混合描述：每个音频片段的有效音量（考虑淡入淡出）

### 预览渲染策略

| 参数类型 | 渲染方式 | 延迟 |
|----------|----------|------|
| 速度调整 | 更新片段位置，重新请求视频帧 | <50ms |
| 裁剪/缩放 | CSS transform 或 Canvas drawImage 裁剪 | <50ms |
| 旋转/翻转 | CSS transform | <50ms |
| 调色（简单） | Canvas 像素操作或 WebGL shader | 50-100ms |
| 调色（复杂） | 手动刷新后重新计算 | 200-500ms |
| 叠加文字 | Canvas 2D drawText | <50ms |
| 叠加图片 | Canvas drawImage | <50ms |
| 音频调整 | Web Audio API 实时混合 | 实时 |

## 滤镜管线

### FilterPipeline

为单个视频片段生成 FFmpeg filter 字符串：

1. 裁剪 → crop
2. 缩放 → scale
3. 旋转/翻转 → transpose/hflip/vflip
4. 调色 → eq/colorchannelmixer/format
5. 模糊/锐化 → gblur/unsharp
6. 速度调整 → setpts
7. 叠加 → drawtext/overlay

## 导出编排

### 导出策略：两遍导出

```
第一遍：片段预处理
  对每个需要处理的片段独立处理：裁剪 → 变换 → 调色 → 速度 → 叠加
  输出中间文件

第二遍：合成导出
  - 视频：concat 所有片段
  - 音频：amix 混合所有音频轨道
  - 输出最终文件
```

### 导出设置

```javascript
const ExportSettings = {
  format: 'mp4',           // mp4 | webm
  videoCodec: 'libx264',   // libx264 | libvpx-vp9
  audioCodec: 'aac',       // aac | libopus
  crf: 23,                 // 0-51
  preset: 'veryfast',      // ultrafast | superfast | veryfast | faster | fast | medium
  resolution: 'source',    // source | 1080p | 720p | 480p
  fps: 'source',           // source | 24 | 25 | 30 | 60
  videoBitrate: null,      // null = CRF 模式
  audioBitrate: '192k',
};
```

### 进度报告

| 阶段 | 进度范围 | 说明 |
|------|----------|------|
| 预处理片段 | 0-50% | 每个片段均匀分配 |
| 合成视频 | 50-100% | FFmpeg 合成进度 |
| 完成 | 100% | 返回 blob |

## 时间线 UI

### 布局

- 左侧：文件库（可拖拽到时间线）
- 中间：预览画布 + 播放控制条
- 右侧：参数面板
- 底部：时间线（多轨道）

### 交互

| 操作 | 行为 |
|------|------|
| 拖拽片段到时间线 | 创建新片段 |
| 拖拽片段在轨道内移动 | 调整位置 |
| 拖拽片段边缘 | trim |
| 双击片段 | split |
| 右键片段 | 菜单：拆分/复制/删除/属性 |
| 滚轮 | 时间线缩放 |
| 空格 | 播放/暂停 |
| 拖动播放头 | 预览跳转 |

### 轨道管理

- 视频轨：可有多条，上层覆盖下层
- 音频轨：可有多条，自动混合
- 叠加轨：可有多条
- 每条轨道有：静音/锁定/隐藏按钮

## 平台差异

| 维度 | 网页版 | 桌面版 |
|------|--------|--------|
| 预览渲染 | Canvas 2D + WebCodecs | QML VideoOutput + QPainter |
| 导出引擎 | FFmpeg WASM (单线程) | 本地 FFmpeg (多线程) |
| 文件系统 | 浏览器虚拟 FS | 原生文件系统 |
| 内存限制 | ~2-4 GB (WASM) | 系统可用内存 |
| 进度反馈 | FFmpeg progress 事件 | FFmpeg stderr 解析 |
| 取消机制 | terminate Worker | 进程 kill |

### 共享核心层接口

核心层通过依赖注入提供平台能力，不依赖任何平台 API。网页版和桌面版分别实现适配器。

## 文件组织

```
web/lib/video_edit/
├── model.js              # TimelineModel, Clip, Track
├── engine.js             # EditEngine, 命令模式
├── params.js             # ClipParams 定义与校验
├── preview.js            # PreviewCalculator
├── filters.js            # FilterPipeline
├── export.js             # ExportOrchestrator
├── core.js               # VideoEditCore, 平台适配器接口
├── web/
│   ├── adapter.js        # WebAdapter (FFmpeg WASM)
│   └── renderer.js       # WebPreviewRenderer (Canvas)
└── desktop/
    └── adapter.js        # DesktopAdapter

web/pages/video_edit.js   # 网页版时间线 UI
gui/video_edit/
├── __init__.py
├── timeline_widget.py    # 时间线 QWidget
├── preview_widget.py     # 预览 QWidget
├── params_panel.py       # 参数面板 QWidget
├── exporter.py           # NativeExporter
└── bridge.py             # QWebChannel 桥接
```

## 测试策略

| 层级 | 测试对象 | 框架 | 覆盖率要求 |
|------|----------|------|------------|
| 核心逻辑 | model/engine/params/preview/filters/export | Node.js test | >=98% |
| Web 适配器 | web/adapter.js, web/renderer.js | Node.js test | >=98% |
| Web UI | pages/video_edit.js | Node.js test (DOM mock) | 关键路径 |
| 桌面核心 | gui/video_edit/*.py | pytest | >=98% |
| 桌面 UI | timeline/preview/params widget | pytest offscreen | 关键路径 |

## 实施阶段

| 阶段 | 内容 | 交付物 | 预估 |
|------|------|--------|------|
| P0 | 核心数据模型 + EditEngine | model.js/engine.js + 测试 | 2-3 天 |
| P1 | PreviewCalculator + FilterPipeline | preview.js/filters.js + 测试 | 2-3 天 |
| P2 | ExportOrchestrator + WebAdapter | export.js/web/adapter.js + 测试 | 2-3 天 |
| P3 | 网页版时间线 UI | pages/video_edit.js + 样式 | 3-4 天 |
| P4 | 桌面版时间线 UI | gui/video_edit/*.py | 3-4 天 |
| P5 | 集成测试 + 优化 | 测试 + 性能调优 | 2-3 天 |

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| FFmpeg WASM 内存不足 | 大文件导出失败 | 分段处理 + 及时清理中间文件 |
| Canvas 预览性能不足 | 复杂时间线卡顿 | 降低预览分辨率 + 手动刷新 |
| 桌面版 QML 预览同步 | 音画不同步 | 使用 QMediaPlayer 内置同步 |
| 滤镜图过于复杂 | FFmpeg 报错 | 分步构建 + 单元测试覆盖 |
