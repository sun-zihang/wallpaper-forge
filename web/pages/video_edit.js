// web/pages/video_edit.js
import { TimelineModel, Track, Clip, createDefaultParams } from "../lib/video_edit/model.js";
import { EditEngine, SplitClipCommand, RemoveClipCommand, MoveClipCommand, TrimClipCommand, AdjustParamsCommand } from "../lib/video_edit/engine.js";
import { PreviewCalculator } from "../lib/video_edit/preview.js";
import { WebAdapter } from "../lib/video_edit/web/adapter.js";
import { WebPreviewRenderer } from "../lib/video_edit/web/renderer.js";
import { ExportOrchestrator } from "../lib/video_edit/export.js";
import { ensureFFmpeg } from "../lib/video_bridge.js";
import { probeVideoDuration } from "../lib/video_limits.js";
import { validateSelection } from "../lib/selection.js";
import { downloadBlob } from "../lib/download.js";
import { friendlyError } from "../lib/errors.js";
import { setStatus, getRenderToken } from "../app.js";

const PREVIEW_SCALE = 0.5;
const MIN_SPLIT_SEC = 0.1;
const MIN_TRIM_SEC = 0.1;
const VIDEO_EXTENSIONS = [".mp4", ".webm", ".mov", ".mkv"];

export function mountVideoEdit(root, deps = {}) {
  const raf = deps.requestAnimationFrame || ((fn) => globalThis.requestAnimationFrame(fn));
  const loadFFmpeg = deps.ensureFFmpeg || ensureFFmpeg;
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

  const $ = (sel) => root.querySelector(sel);
  const els = {
    backBtn: $("#backBtn"),
    undoBtn: $("#undoBtn"),
    redoBtn: $("#redoBtn"),
    exportBtn: $("#exportBtn"),
    addFiles: $("#addFiles"),
    files: $("#files"),
    fileList: $("#fileList"),
    stage: $("#stage"),
    canvas: $("#previewCanvas"),
    playBtn: $("#playBtn"),
    timeInfo: $("#timeInfo"),
    paramsBody: $("#paramsBody"),
    timeline: $("#timeline"),
    ruler: $("#ruler"),
    tracks: $("#tracks"),
    err: $("#err"),
  };

  const renderer = new WebPreviewRenderer(els.canvas);
  renderer.setQuality(PREVIEW_SCALE);

  const state = {
    fileEntries: [],
    selectedFileIndex: -1,
    selectedClipId: null,
    currentTime: 0,
    playing: false,
    playLastTs: 0,
    previewQueued: false,
    exporting: false,
    dragFileIndex: -1,
    renderGen: 0,
  };

  let selectedClipEl = null;

  function stale() {
    return token !== getRenderToken();
  }

  function showError(e) {
    els.err.textContent = friendlyError(e);
  }

  function fmtTime(sec) {
    if (!Number.isFinite(sec) || sec < 0) sec = 0;
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  function timelineDuration() {
    return Math.max(timeline.duration, 10);
  }

  function updateTimeInfo() {
    els.timeInfo.textContent = `${fmtTime(state.currentTime)} / ${fmtTime(timeline.duration)}`;
  }

  function afterEdit(refreshParams = false) {
    if (stale()) return;
    renderTimeline();
    updateTimeInfo();
    schedulePreview();
    if (refreshParams) renderParamsPanel();
  }

  function schedulePreview() {
    if (state.previewQueued) return;
    state.previewQueued = true;
    raf(() => {
      state.previewQueued = false;
      if (stale()) return;
      renderPreview();
    });
  }

  async function renderPreview() {
    const gen = ++state.renderGen;
    const frame = calculator.getFrameAt(timeline, state.currentTime);
    try {
      await renderer.render(frame);
    } catch (e) {
      if (gen === state.renderGen) showError(e);
      return;
    }
    if (gen !== state.renderGen) return;
    updateTimeInfo();
  }

  function renderFileList() {
    const list = els.fileList;
    list.innerHTML = "";
    state.fileEntries.forEach((entry, i) => {
      const div = document.createElement("div");
      div.className = "edit-file" + (i === state.selectedFileIndex ? " selected" : "");
      div.setAttribute("draggable", "true");
      const nameEl = document.createElement("span");
      nameEl.className = "edit-file-name";
      nameEl.textContent = entry.file.name;
      const durEl = document.createElement("span");
      durEl.className = "edit-file-dur";
      durEl.textContent = entry.duration != null ? fmtTime(entry.duration) : "";
      div.appendChild(nameEl);
      div.appendChild(durEl);
      div.addEventListener("click", () => {
        state.selectedFileIndex = i;
        renderFileList();
      });
      div.addEventListener("dragstart", (ev) => {
        state.dragFileIndex = i;
        if (ev.dataTransfer) {
          ev.dataTransfer.setData("text/plain", String(i));
          ev.dataTransfer.effectAllowed = "copy";
        }
      });
      div.addEventListener("dragend", () => {
        state.dragFileIndex = -1;
      });
      list.appendChild(div);
    });
  }

  function addFiles(files) {
    const check = validateSelection(files, { extensions: VIDEO_EXTENSIONS });
    if (!check.ok) {
      showError(new Error(check.errors.map((e) => `${e.name}：${e.reason}`).join("\n")));
      return;
    }
    const added = check.files.map((f) => ({ file: f, url: URL.createObjectURL(f), duration: null }));
    state.fileEntries.push(...added);
    if (state.selectedFileIndex < 0 && added.length) state.selectedFileIndex = 0;
    renderFileList();
    for (const entry of added) {
      probeVideoDuration(entry.file).then((sec) => {
        if (stale()) return;
        entry.duration = sec;
        renderFileList();
      });
    }
  }

  function addClipFromFile(entry) {
    const videoTrack = timeline.tracks.find((t) => t.type === "video");
    if (!videoTrack) return;
    const dur = entry.duration != null ? entry.duration : 10;
    const clip = new Clip({
      sourceFile: entry.file,
      timelineIn: timeline.duration,
      sourceIn: 0,
      sourceOut: dur,
      speed: 1,
      params: createDefaultParams(),
    });
    videoTrack.addClip(clip);
    state.selectedClipId = clip.id;
    afterEdit(true);
  }

  function renderRuler() {
    const ruler = els.ruler;
    ruler.innerHTML = "";
    const dur = timelineDuration();
    const step = dur > 60 ? 10 : dur > 30 ? 5 : 1;
    for (let t = 0; t <= dur + 1e-6; t += step) {
      const tick = document.createElement("div");
      tick.className = "tl-tick";
      tick.style.left = `${(t / dur) * 100}%`;
      const label = document.createElement("span");
      label.textContent = fmtTime(t);
      tick.appendChild(label);
      ruler.appendChild(tick);
    }
  }

  function renderPlayhead() {
    let head = els.tracks.querySelector(".tl-playhead");
    if (!head) {
      head = document.createElement("div");
      head.className = "tl-playhead";
      els.tracks.appendChild(head);
      head.addEventListener("pointerdown", (ev) => {
        ev.preventDefault?.();
        const move = (e) => {
          const r = els.tracks.getBoundingClientRect();
          const pct = Math.max(0, Math.min(1, (e.clientX - r.left) / (r.width || 1)));
          state.currentTime = pct * timelineDuration();
          renderPlayhead();
          updateTimeInfo();
          schedulePreview();
        };
        const up = () => {
          head.removeEventListener("pointermove", move);
          head.removeEventListener("pointerup", up);
        };
        head.addEventListener("pointermove", move);
        head.addEventListener("pointerup", up);
      });
    }
    head.style.left = `${(state.currentTime / timelineDuration()) * 100}%`;
  }

  function renderTimeline() {
    const tracksEl = els.tracks;
    tracksEl.innerHTML = "";
    selectedClipEl = null;
    const dur = timelineDuration();
    for (const track of timeline.tracks) {
      const trackEl = document.createElement("div");
      trackEl.className = "tl-track";
      trackEl.dataset.trackId = track.id;
      const label = document.createElement("div");
      label.className = "tl-track-label";
      label.textContent = track.name;
      trackEl.appendChild(label);
      const lane = document.createElement("div");
      lane.className = "tl-lane";
      lane.dataset.trackId = track.id;
      for (const clip of track.clips) {
        const clipEl = buildClipEl(clip, track, dur);
        lane.appendChild(clipEl);
        if (clip.id === state.selectedClipId) selectedClipEl = clipEl;
      }
      lane.addEventListener("pointerdown", (ev) => {
        if (ev.target !== lane) return;
        const r = lane.getBoundingClientRect();
        const pct = Math.max(0, Math.min(1, (ev.clientX - r.left) / (r.width || 1)));
        state.currentTime = pct * dur;
        renderPlayhead();
        updateTimeInfo();
        schedulePreview();
      });
      trackEl.appendChild(lane);
      tracksEl.appendChild(trackEl);
    }
    renderRuler();
    renderPlayhead();
  }

  function buildClipEl(clip, track, dur) {
    const el = document.createElement("div");
    el.className = "tl-clip" + (clip.id === state.selectedClipId ? " selected" : "");
    el.dataset.clipId = clip.id;
    el.style.left = `${(clip.timelineIn / dur) * 100}%`;
    el.style.width = `${Math.max(0.5, (clip.duration / dur) * 100)}%`;
    const name = document.createElement("span");
    name.className = "tl-clip-name";
    name.textContent = clip.sourceFile?.name || "片段";
    el.appendChild(name);
    const trimL = document.createElement("div");
    trimL.className = "tl-trim left";
    trimL.dataset.handle = "left";
    const trimR = document.createElement("div");
    trimR.className = "tl-trim right";
    trimR.dataset.handle = "right";
    el.appendChild(trimL);
    el.appendChild(trimR);

    el.addEventListener("click", (ev) => {
      ev.stopPropagation?.();
      selectClip(clip.id, el);
    });
    el.addEventListener("contextmenu", (ev) => {
      ev.preventDefault?.();
      showClipMenu(clip);
    });
    el.addEventListener("pointerdown", (ev) => {
      if (ev.target !== el) return;
      startClipMove(ev, clip, track, el);
    });
    trimL.addEventListener("pointerdown", (ev) => {
      ev.stopPropagation?.();
      startTrim(ev, clip, "left", el);
    });
    trimR.addEventListener("pointerdown", (ev) => {
      ev.stopPropagation?.();
      startTrim(ev, clip, "right", el);
    });
    return el;
  }

  function laneSecPerPx(lane) {
    const r = lane.getBoundingClientRect();
    return timelineDuration() / (r.width || 1);
  }

  function startClipMove(ev, clip, track, el) {
    ev.preventDefault?.();
    const lane = el.parentNode;
    const startX = ev.clientX;
    const startIn = clip.timelineIn;
    const secPerPx = laneSecPerPx(lane);
    const dur = timelineDuration();
    let currentIn = startIn;
    let moved = false;
    const move = (e) => {
      const dx = e.clientX - startX;
      if (Math.abs(dx) < 2) return;
      moved = true;
      currentIn = Math.max(0, Math.min(dur - clip.duration, startIn + dx * secPerPx));
      el.style.left = `${(currentIn / dur) * 100}%`;
    };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      if (!moved) return;
      if (Math.abs(currentIn - startIn) < MIN_TRIM_SEC) return;
      engine.execute(new MoveClipCommand(clip.id, track.id, currentIn));
      afterEdit(true);
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  }

  function startTrim(ev, clip, edge, el) {
    ev.preventDefault?.();
    const lane = el.parentNode;
    const startX = ev.clientX;
    const secPerPx = laneSecPerPx(lane);
    const dur = timelineDuration();
    const startSourceIn = clip.sourceIn;
    const startSourceOut = clip.sourceOut;
    let newSourceIn = startSourceIn;
    let newSourceOut = startSourceOut;
    const move = (e) => {
      const dx = (e.clientX - startX) * secPerPx;
      if (edge === "left") {
        newSourceIn = Math.max(0, Math.min(startSourceIn + dx, startSourceOut - MIN_TRIM_SEC));
        el.style.left = `${(clip.timelineIn / dur) * 100}%`;
      } else {
        newSourceOut = Math.max(startSourceIn + MIN_TRIM_SEC, Math.min(startSourceOut + dx, dur));
      }
      el.style.width = `${Math.max(0.5, ((newSourceOut - newSourceIn) / clip.speed / dur) * 100)}%`;
    };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      if (newSourceIn === startSourceIn && newSourceOut === startSourceOut) return;
      engine.execute(new TrimClipCommand(clip.id, newSourceIn, newSourceOut));
      afterEdit();
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  }

  function selectClip(clipId, clipEl = null) {
    if (selectedClipEl) selectedClipEl.classList.remove("selected");
    state.selectedClipId = clipId;
    selectedClipEl = clipEl;
    if (selectedClipEl) selectedClipEl.classList.add("selected");
    renderParamsPanel();
    schedulePreview();
  }

  function splitClipAtPlayhead(clip) {
    const t = state.currentTime;
    if (t <= clip.timelineIn + MIN_SPLIT_SEC || t >= clip.timelineIn + clip.duration - MIN_SPLIT_SEC) {
      showError("播放头不在片段内，无法拆分");
      return;
    }
    engine.execute(new SplitClipCommand(clip.id, t - clip.timelineIn));
    afterEdit(true);
  }

  function removeSelectedClip() {
    if (!state.selectedClipId) return;
    engine.execute(new RemoveClipCommand(state.selectedClipId));
    state.selectedClipId = null;
    afterEdit(true);
  }

  let clipMenu = null;
  function showClipMenu(clip) {
    closeClipMenu();
    clipMenu = document.createElement("div");
    clipMenu.className = "clip-menu";
    const splitItem = document.createElement("button");
    splitItem.type = "button";
    splitItem.textContent = "拆分";
    splitItem.addEventListener("click", () => {
      closeClipMenu();
      splitClipAtPlayhead(clip);
    });
    const delItem = document.createElement("button");
    delItem.type = "button";
    delItem.textContent = "删除";
    delItem.addEventListener("click", () => {
      closeClipMenu();
      removeSelectedClip();
    });
    clipMenu.appendChild(splitItem);
    clipMenu.appendChild(delItem);
    document.body.appendChild(clipMenu);
  }

  function closeClipMenu() {
    if (clipMenu && clipMenu.parentNode) clipMenu.parentNode.removeChild(clipMenu);
    clipMenu = null;
  }

  function sectionTitle(text) {
    const h = document.createElement("p");
    h.className = "panel-title";
    h.textContent = text;
    return h;
  }

  function fieldWrap(labelText, control) {
    const wrap = document.createElement("div");
    wrap.className = "field";
    const label = document.createElement("label");
    label.textContent = labelText;
    wrap.appendChild(label);
    wrap.appendChild(control);
    return wrap;
  }

  function addRange(parent, label, id, min, max, step, value, onInput) {
    const input = document.createElement("input");
    input.type = "range";
    input.id = id;
    input.min = String(min);
    input.max = String(max);
    input.step = String(step);
    input.value = String(value);
    const valEl = document.createElement("span");
    valEl.className = "field-val";
    valEl.textContent = String(value);
    input.addEventListener("input", () => {
      const v = Number(input.value);
      valEl.textContent = String(v);
      onInput(v);
    });
    const wrap = fieldWrap(label, input);
    wrap.appendChild(valEl);
    parent.appendChild(wrap);
    return input;
  }

  function addCheck(parent, label, id, checked, onChange) {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.id = id;
    input.checked = !!checked;
    input.addEventListener("change", () => onChange(input.checked));
    const wrap = document.createElement("div");
    wrap.className = "field inline";
    const lab = document.createElement("label");
    lab.textContent = label;
    wrap.appendChild(input);
    wrap.appendChild(lab);
    parent.appendChild(wrap);
    return input;
  }

  function addSelect(parent, label, id, value, options, onChange) {
    const input = document.createElement("select");
    input.id = id;
    for (const [v, text] of options) {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = text;
      input.appendChild(opt);
    }
    input.value = value;
    input.addEventListener("change", () => onChange(input.value));
    parent.appendChild(fieldWrap(label, input));
    return input;
  }

  function addNumber(parent, label, id, min, max, step, value, onChange, disabled = false) {
    const input = document.createElement("input");
    input.type = "number";
    input.id = id;
    input.min = String(min);
    input.max = String(max);
    input.step = String(step);
    input.value = String(value);
    input.disabled = disabled;
    input.addEventListener("change", () => onChange(Number(input.value)));
    parent.appendChild(fieldWrap(label, input));
    return input;
  }

  function addText(parent, label, id, value, onChange, type = "text") {
    const input = document.createElement("input");
    input.type = type;
    input.id = id;
    input.value = value;
    input.addEventListener("change", () => onChange(input.value));
    parent.appendChild(fieldWrap(label, input));
    return input;
  }

  function textOverlay(clip, partial) {
    const prev = clip.params.overlay && clip.params.overlay.type === "text" ? clip.params.overlay : {};
    return {
      type: "text",
      text: partial.text ?? prev.text ?? "",
      fontSize: partial.fontSize ?? prev.fontSize ?? 24,
      fontColor: partial.fontColor ?? prev.fontColor ?? "#ffffff",
      position: {
        x: partial.x ?? prev.position?.x ?? 50,
        y: partial.y ?? prev.position?.y ?? 50,
      },
      opacity: partial.opacity ?? prev.opacity ?? 1,
    };
  }

  function applyCrop(clip, partial) {
    const base = clip.params.transform.crop || { x: 0, y: 0, width: 1280, height: 720 };
    engine.execute(new AdjustParamsCommand(clip.id, { transform: { crop: { ...base, ...partial } } }));
    afterEdit();
  }

  function renderParamsPanel() {
    const body = els.paramsBody;
    body.innerHTML = "";
    const clip = timeline.findClip(state.selectedClipId);
    if (!clip) {
      const p = document.createElement("p");
      p.className = "placeholder";
      p.textContent = "选择时间线上的片段";
      body.appendChild(p);
      return;
    }
    const params = clip.params;

    const playSec = document.createElement("div");
    playSec.className = "param-section";
    playSec.appendChild(sectionTitle("播放"));
    addRange(playSec, "速度", "speed", 0.1, 10, 0.1, clip.speed, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { speed: v }));
      afterEdit();
    });
    addRange(playSec, "音量", "volume", 0, 2, 0.05, params.audio.volume, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { audio: { volume: v } }));
      afterEdit();
    });
    addRange(playSec, "淡入", "fadeIn", 0, 5, 0.1, params.audio.fadeIn, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { audio: { fadeIn: v } }));
      afterEdit();
    });
    addRange(playSec, "淡出", "fadeOut", 0, 5, 0.1, params.audio.fadeOut, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { audio: { fadeOut: v } }));
      afterEdit();
    });
    body.appendChild(playSec);

    const videoSec = document.createElement("div");
    videoSec.className = "param-section";
    videoSec.appendChild(sectionTitle("画面"));
    addSelect(videoSec, "旋转", "rotation", String(params.transform.rotation), [
      ["0", "0°"],
      ["90", "90°"],
      ["180", "180°"],
      ["270", "270°"],
    ], (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { transform: { rotation: Number(v) } }));
      afterEdit();
    });
    addCheck(videoSec, "水平翻转", "flipH", params.transform.flipH, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { transform: { flipH: v } }));
      afterEdit();
    });
    addCheck(videoSec, "垂直翻转", "flipV", params.transform.flipV, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { transform: { flipV: v } }));
      afterEdit();
    });
    addRange(videoSec, "缩放", "scale", 0.1, 3, 0.05, params.transform.scale, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { transform: { scale: v } }));
      afterEdit();
    });
    const crop = params.transform.crop || { x: 0, y: 0, width: 1280, height: 720 };
    addCheck(videoSec, "启用裁剪", "cropOn", !!params.transform.crop, (v) => {
      const next = v ? params.transform.crop || { x: 0, y: 0, width: 1280, height: 720 } : null;
      engine.execute(new AdjustParamsCommand(clip.id, { transform: { crop: next } }));
      afterEdit(true);
    });
    addNumber(videoSec, "裁剪 X", "cropX", 0, 10000, 1, crop.x, (v) => applyCrop(clip, { x: v }), !params.transform.crop);
    addNumber(videoSec, "裁剪 Y", "cropY", 0, 10000, 1, crop.y, (v) => applyCrop(clip, { y: v }), !params.transform.crop);
    addNumber(videoSec, "裁剪宽", "cropW", 1, 10000, 1, crop.width, (v) => applyCrop(clip, { width: v }), !params.transform.crop);
    addNumber(videoSec, "裁剪高", "cropH", 1, 10000, 1, crop.height, (v) => applyCrop(clip, { height: v }), !params.transform.crop);
    body.appendChild(videoSec);

    const colorSec = document.createElement("div");
    colorSec.className = "param-section";
    colorSec.appendChild(sectionTitle("调色"));
    addRange(colorSec, "亮度", "brightness", -1, 1, 0.05, params.filters.brightness, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { filters: { brightness: v } }));
      afterEdit();
    });
    addRange(colorSec, "对比度", "contrast", -1, 1, 0.05, params.filters.contrast, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { filters: { contrast: v } }));
      afterEdit();
    });
    addRange(colorSec, "饱和度", "saturation", -1, 1, 0.05, params.filters.saturation, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { filters: { saturation: v } }));
      afterEdit();
    });
    addRange(colorSec, "色相", "hue", 0, 360, 1, params.filters.hue, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { filters: { hue: v } }));
      afterEdit();
    });
    addCheck(colorSec, "灰度", "grayscale", params.filters.grayscale, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { filters: { grayscale: v } }));
      afterEdit();
    });
    addCheck(colorSec, "怀旧", "sepia", params.filters.sepia, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { filters: { sepia: v } }));
      afterEdit();
    });
    addRange(colorSec, "模糊", "blur", 0, 10, 0.5, params.filters.blur, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { filters: { blur: v } }));
      afterEdit();
    });
    addRange(colorSec, "锐化", "sharpen", 0, 5, 0.1, params.filters.sharpen, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { filters: { sharpen: v } }));
      afterEdit();
    });
    body.appendChild(colorSec);

    const ov = params.overlay && params.overlay.type === "text" ? params.overlay : null;
    const ovSec = document.createElement("div");
    ovSec.className = "param-section";
    ovSec.appendChild(sectionTitle("叠加"));
    addCheck(ovSec, "文字叠加", "overlayOn", !!ov, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { overlay: v ? textOverlay(clip, {}) : null }));
      afterEdit(true);
    });
    addText(ovSec, "文字内容", "overlayText", ov?.text || "", (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { overlay: textOverlay(clip, { text: v }) }));
      afterEdit();
    });
    addNumber(ovSec, "字号", "overlaySize", 8, 200, 1, ov?.fontSize || 24, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { overlay: textOverlay(clip, { fontSize: v }) }));
      afterEdit();
    }, !ov);
    addText(ovSec, "颜色", "overlayColor", ov?.fontColor || "#ffffff", (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { overlay: textOverlay(clip, { fontColor: v }) }));
      afterEdit();
    }, "color");
    addNumber(ovSec, "位置 X", "overlayX", 0, 100, 1, ov?.position?.x ?? 50, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { overlay: textOverlay(clip, { x: v }) }));
      afterEdit();
    }, !ov);
    addNumber(ovSec, "位置 Y", "overlayY", 0, 100, 1, ov?.position?.y ?? 50, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { overlay: textOverlay(clip, { y: v }) }));
      afterEdit();
    }, !ov);
    addRange(ovSec, "透明度", "overlayOpacity", 0, 1, 0.05, ov?.opacity ?? 1, (v) => {
      engine.execute(new AdjustParamsCommand(clip.id, { overlay: textOverlay(clip, { opacity: v }) }));
      afterEdit();
    });
    body.appendChild(ovSec);
  }

  function play() {
    if (state.playing) return;
    if (timeline.duration <= 0) return;
    if (state.currentTime >= timeline.duration) state.currentTime = 0;
    state.playing = true;
    state.playLastTs = null;
    els.playBtn.textContent = "⏸";
    raf(tick);
  }

  function pause() {
    state.playing = false;
    els.playBtn.textContent = "▶";
  }

  function tick(ts) {
    if (!state.playing) return;
    if (stale()) {
      pause();
      return;
    }
    if (state.playLastTs == null) state.playLastTs = ts;
    const dt = Math.min(1, Math.max(0, (ts - state.playLastTs) / 1000));
    state.playLastTs = ts;
    state.currentTime += dt;
    if (state.currentTime >= timeline.duration) {
      state.currentTime = timeline.duration;
      pause();
    }
    renderPlayhead();
    updateTimeInfo();
    schedulePreview();
    if (state.playing) raf(tick);
  }

  function onKeyDown(ev) {
    if (stale()) return;
    const tag = ev.target && ev.target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || tag === "BUTTON") return;
    const mod = ev.ctrlKey || ev.metaKey;
    const key = ev.key;
    if ((key === "Delete" || key === "Backspace") && state.selectedClipId) {
      ev.preventDefault?.();
      removeSelectedClip();
    } else if (mod && key.toLowerCase() === "z") {
      ev.preventDefault?.();
      if (ev.shiftKey) {
        if (engine.redo()) afterEdit(true);
      } else if (engine.undo()) {
        afterEdit(true);
      }
    } else if (mod && key.toLowerCase() === "y") {
      ev.preventDefault?.();
      if (engine.redo()) afterEdit(true);
    } else if (key === " ") {
      ev.preventDefault?.();
      if (state.playing) pause();
      else play();
    }
  }

  let exportDialog = null;

  function setExportProgress(pct, msg) {
    if (!exportDialog) return;
    const bar = exportDialog.querySelector(".export-progress-bar");
    const text = exportDialog.querySelector(".export-progress-text");
    if (bar && pct >= 0) bar.style.width = `${pct}%`;
    if (text && msg) text.textContent = msg;
  }

  function closeExportDialog() {
    if (exportDialog && exportDialog.parentNode) exportDialog.parentNode.removeChild(exportDialog);
    exportDialog = null;
  }

  function openExportDialog() {
    closeExportDialog();
    const overlay = document.createElement("div");
    overlay.className = "export-overlay";
    const dialog = document.createElement("div");
    dialog.className = "export-dialog";
    overlay.appendChild(dialog);

    const title = document.createElement("p");
    title.className = "panel-title";
    title.textContent = "导出设置";
    dialog.appendChild(title);

    const fmt = addSelect(dialog, "格式", "fmt", "mp4", [
      ["mp4", "MP4"],
      ["webm", "WebM"],
    ], () => {});
    const codec = addSelect(dialog, "编码器", "codec", "libx264", [
      ["libx264", "H.264 (libx264)"],
      ["libx265", "H.265 (libx265)"],
      ["libvpx-vp9", "VP9 (libvpx-vp9)"],
    ], () => {});
    const crf = addRange(dialog, "质量 (CRF)", "crf", 0, 51, 1, 23, () => {});
    const preset = addSelect(dialog, "预设", "preset", "veryfast", [
      ["ultrafast", "ultrafast"],
      ["superfast", "superfast"],
      ["veryfast", "veryfast"],
      ["faster", "faster"],
      ["fast", "fast"],
      ["medium", "medium"],
      ["slow", "slow"],
      ["slower", "slower"],
      ["veryslow", "veryslow"],
    ], () => {});

    const progress = document.createElement("div");
    progress.className = "export-progress";
    const bar = document.createElement("div");
    bar.className = "export-progress-bar";
    bar.style.width = "0%";
    progress.appendChild(bar);
    const msg = document.createElement("p");
    msg.className = "export-progress-text";
    msg.textContent = "";
    dialog.appendChild(progress);
    dialog.appendChild(msg);

    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "btn secondary";
    cancelBtn.id = "exportCancel";
    cancelBtn.textContent = "取消";
    cancelBtn.addEventListener("click", closeExportDialog);
    const goBtn = document.createElement("button");
    goBtn.type = "button";
    goBtn.className = "btn";
    goBtn.id = "exportGo";
    goBtn.textContent = "开始导出";
    goBtn.addEventListener("click", () => {
      runExport({
        format: fmt.value,
        videoCodec: codec.value,
        crf: Number(crf.value),
        preset: preset.value,
      });
    });
    const btnRow = document.createElement("div");
    btnRow.className = "export-actions";
    btnRow.appendChild(cancelBtn);
    btnRow.appendChild(goBtn);
    dialog.appendChild(btnRow);

    document.body.appendChild(overlay);
    exportDialog = overlay;
  }

  function extOf(name) {
    const m = /\.([^.]+)$/.exec(name || "");
    return m ? m[1] : "mp4";
  }

  async function materializeSources(adapter) {
    const sources = new Map();
    let i = 0;
    for (const track of timeline.tracks) {
      for (const clip of track.clips) {
        if (clip.sourceFile && typeof clip.sourceFile !== "string" && !sources.has(clip.sourceFile)) {
          const name = `src_${i++}.${extOf(clip.sourceFile.name)}`;
          await adapter.writeFile(name, clip.sourceFile);
          sources.set(clip.sourceFile, name);
        }
      }
    }
    if (!sources.size) return timeline;
    return {
      tracks: timeline.tracks.map((track) => ({
        ...track,
        clips: track.clips.map((clip) => {
          const name = sources.get(clip.sourceFile);
          return name ? { ...clip, sourceFile: name } : clip;
        }),
      })),
    };
  }

  async function runExport(options) {
    if (state.exporting) return;
    const hasClips = timeline.tracks.some((t) => t.type === "video" && t.clips.length > 0);
    if (!hasClips) {
      showError("时间线上没有片段");
      return;
    }
    state.exporting = true;
    try {
      setStatus("正在加载视频引擎…");
      setExportProgress(0, "正在加载视频引擎…");
      const ff = await loadFFmpeg((msg) => {
        setStatus(msg);
        setExportProgress(-1, msg);
      });
      const adapter = new WebAdapter(ff);
      const exportTimeline = await materializeSources(adapter);
      const orchestrator = new ExportOrchestrator(exportTimeline, options, adapter);
      const result = await orchestrator.export((pct, msg) => setExportProgress(pct, msg));
      downloadBlob(result.blob, result.filename);
      setStatus("导出完成");
      setExportProgress(100, "导出完成");
    } catch (e) {
      showError(e);
      setStatus("导出失败");
    } finally {
      state.exporting = false;
      closeExportDialog();
    }
  }

  els.backBtn.addEventListener("click", () => {
    location.hash = "#/video";
  });
  els.undoBtn.addEventListener("click", () => {
    if (engine.undo()) afterEdit(true);
  });
  els.redoBtn.addEventListener("click", () => {
    if (engine.redo()) afterEdit(true);
  });
  els.addFiles.addEventListener("click", () => els.files.click());
  els.files.addEventListener("change", () => {
    const picked = [...(els.files.files || [])];
    els.files.value = "";
    if (picked.length) addFiles(picked);
  });
  els.playBtn.addEventListener("click", () => {
    if (state.playing) pause();
    else play();
  });
  els.exportBtn.addEventListener("click", openExportDialog);
  els.tracks.addEventListener("dblclick", (ev) => {
    let node = ev.target;
    while (node && node !== els.tracks) {
      if (node.dataset && node.dataset.clipId) {
        const clip = timeline.findClip(node.dataset.clipId);
        if (clip) splitClipAtPlayhead(clip);
        return;
      }
      node = node.parentNode;
    }
  });
  document.addEventListener("keydown", onKeyDown);

  const filesAside = root.querySelector(".edit-files");
  filesAside.addEventListener("dragover", (ev) => {
    ev.preventDefault?.();
    filesAside.classList.add("hot");
  });
  filesAside.addEventListener("dragleave", () => filesAside.classList.remove("hot"));
  filesAside.addEventListener("drop", (ev) => {
    ev.preventDefault?.();
    filesAside.classList.remove("hot");
    addFiles([...(ev.dataTransfer?.files || [])]);
  });

  els.timeline.addEventListener("dragover", (ev) => ev.preventDefault?.());
  els.timeline.addEventListener("drop", (ev) => {
    ev.preventDefault?.();
    const files = ev.dataTransfer?.files;
    if (files && files.length) {
      addFiles([...files]);
      return;
    }
    if (state.dragFileIndex >= 0 && state.dragFileIndex < state.fileEntries.length) {
      addClipFromFile(state.fileEntries[state.dragFileIndex]);
    }
    state.dragFileIndex = -1;
  });

  renderFileList();
  renderTimeline();
  renderParamsPanel();
  updateTimeInfo();
  schedulePreview();

  return { timeline, engine, state, els };
}
