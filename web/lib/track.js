// web/lib/track.js
// 本地埋点：只写 localStorage（事件有上限），不向任何服务器发送——
// 与「0 上传 / 文件不离开浏览器」的承诺一致。设置页可查看与清除，
// 控制台亦可通过 window.__wcStats() 读取。
import { classifyError } from "./errors.js";

const KEY = "wc.track.v1";
const MAX_EVENTS = 200;

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    const v = raw ? JSON.parse(raw) : null;
    if (!v || typeof v !== "object") return null;
    if (!v.counters || typeof v.counters !== "object") v.counters = {};
    if (!Array.isArray(v.events)) v.events = [];
    if (!v.since) v.since = Date.now();
    return v;
  } catch {
    return null;
  }
}

function save(v) {
  try {
    localStorage.setItem(KEY, JSON.stringify(v));
  } catch { /* storage unavailable */ }
}

function fresh() {
  return { counters: {}, events: [], since: Date.now() };
}

export function bump(key, n = 1) {
  const v = load() || fresh();
  v.counters[key] = (Number(v.counters[key]) || 0) + n;
  save(v);
}

export function track(name, detail) {
  const v = load() || fresh();
  v.counters[name] = (Number(v.counters[name]) || 0) + 1;
  const ev = { t: Date.now(), name };
  if (detail) Object.assign(ev, detail);
  v.events.push(ev);
  if (v.events.length > MAX_EVENTS) v.events.splice(0, v.events.length - MAX_EVENTS);
  save(v);
}

export function trackUpload(count) {
  track("files_added", { n: count | 0 });
}

export function trackStart() {
  bump("start");
  return Date.now();
}

export function trackEnd(t0) {
  bump("runs");
  if (t0) bump("ms_total", Math.max(0, Date.now() - t0));
}

export function trackFailure(e) {
  const { category } = classifyError(e);
  bump(`failed:${category}`);
}

export function trackModule(hash) {
  const path = hash || "/";
  const name = path === "/" || path === "" ? "home" : path.replace(/^\//, "");
  bump(`module:${name}`);
}

export function trackDesktop(action = "download") {
  track("desktop_cta", { action });
}

export function getStats() {
  const v = load();
  if (!v) {
    return {
      since: 0,
      total: 0,
      counters: {},
      recent: [],
      modules: {},
      failures: {},
      added: 0,
      starts: 0,
      uploadsNotStarted: 0,
      runs: 0,
      avgMs: 0,
      abandoned: 0,
      abandonRate: 0,
      desktop: 0,
    };
  }
  const c = v.counters;
  const modules = {};
  const failures = {};
  let total = 0;
  for (const [k, n] of Object.entries(c)) {
    total += n;
    if (k.startsWith("module:")) modules[k.slice(7)] = n;
    else if (k.startsWith("failed:")) failures[k.slice(7)] = n;
  }
  const added = Number(c.files_added) || 0;
  const starts = Number(c.start) || 0;
  const runs = Number(c.runs) || 0;
  const abandoned = Number(c.abandoned) || 0;
  return {
    since: v.since,
    total,
    counters: c,
    recent: v.events.slice(-20).reverse(),
    modules,
    failures,
    added,
    starts,
    uploadsNotStarted: Math.max(0, Math.min(1, (added - starts) / Math.max(1, added))),
    runs,
    avgMs: runs > 0 ? Math.round((Number(c.ms_total) || 0) / runs) : 0,
    abandoned,
    abandonRate: starts > 0 ? Math.min(1, abandoned / starts) : 0,
    desktop: Number(c.desktop_cta) || 0,
  };
}

export function clearStats() {
  try {
    localStorage.removeItem(KEY);
  } catch { /* ignore */ }
}
