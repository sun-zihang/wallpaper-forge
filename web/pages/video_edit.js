// web/pages/video_edit.js
import { TimelineModel, Track, Clip, createDefaultParams } from "../lib/video_edit/model.js";
import { EditEngine } from "../lib/video_edit/engine.js";
import { PreviewCalculator } from "../lib/video_edit/preview.js";
import { WebAdapter } from "../lib/video_edit/web/adapter.js";
import { WebPreviewRenderer } from "../lib/video_edit/web/renderer.js";
import { ExportOrchestrator } from "../lib/video_edit/export.js";
import { ensureFFmpeg } from "../lib/video_bridge.js";
import { setStatus, getRenderToken } from "../app.js";

export function mountVideoEdit(root) {
  const token = getRenderToken();
  const timeline = new TimelineModel({ id: "edit-tl", name: "未命名" });
  const engine = new EditEngine(timeline);
  const calculator = new PreviewCalculator();

  timeline.addTrack(new Track({ id: "v1", type: "video", name: "视频轨" }));
  timeline.addTrack(new Track({ id: "a1", type: "audio", name: "音频轨" }));
  timeline.addTrack(new Track({ id: "ov1", type: "overlay", name: "叠加轨" }));

  root.innerHTML = `
    <div class="page-head">
      <button type="button" class="btn secondary" id="backBtn">← 返回</button>
      <h1>视频编辑</h1>
      <div>
        <button type="button" class="btn secondary" id="undoBtn">撤销</button>
        <button type="button" class="btn secondary" id="redoBtn">重做</button>
        <button type="button" class="btn" id="exportBtn">导出</button>
      </div>
    </div>
    <div class="video-edit-layout">
      <aside class="edit-files">
        <div class="img-files-head">
          <span>文件</span>
          <button type="button" class="btn secondary" id="addFiles">添加</button>
          <input type="file" id="files" multiple accept="video/*,.mp4,.webm,.mov,.mkv" hidden />
        </div>
        <div class="edit-file-list" id="fileList"></div>
      </aside>
      <div class="edit-preview">
        <div class="preview-stage" id="stage">
          <canvas id="previewCanvas" width="1280" height="720"></canvas>
        </div>
        <div class="video-controls">
          <button type="button" class="btn secondary" id="playBtn">▶</button>
          <span class="preview-info" id="timeInfo">00:00 / 00:00</span>
        </div>
      </div>
      <div class="edit-params">
        <div class="panel">
          <p class="panel-title">片段属性</p>
          <div id="paramsBody">
            <p class="placeholder">选择时间线上的片段</p>
          </div>
        </div>
      </div>
    </div>
    <div class="edit-timeline" id="timeline">
      <div class="timeline-ruler" id="ruler"></div>
      <div class="timeline-tracks" id="tracks"></div>
    </div>
    <pre class="err" id="err"></pre>
  `;
}
