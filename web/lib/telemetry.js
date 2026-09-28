// web/lib/telemetry.js
// Opt-in anonymous aggregate telemetry. OFF by default. Only aggregate
// counters derived from track.js are sent — never file names, event details
// or any file content — and only to an explicitly configured endpoint.
import { getStats } from "./track.js";

const ENABLED_KEY = "wc.telemetry";
const ENDPOINT_KEY = "wc.telemetryEndpoint";
const SENT_KEY = "wc.telemetrySentAt";
const DEFAULT_ENDPOINT = "";
const MIN_INTERVAL_MS = 5 * 60 * 1000;

function storeGet(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function storeSet(key, value) {
  try {
    localStorage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

function storeRemove(key) {
  try {
    localStorage.removeItem(key);
  } catch {
    /* storage unavailable */
  }
}

export function isEnabled() {
  return storeGet(ENABLED_KEY) === "1";
}

export function setEnabled(on) {
  if (on) storeSet(ENABLED_KEY, "1");
  else storeRemove(ENABLED_KEY);
  return isEnabled();
}

export function getEndpoint() {
  return storeGet(ENDPOINT_KEY) || DEFAULT_ENDPOINT;
}

export function setEndpoint(url) {
  if (url) storeSet(ENDPOINT_KEY, url);
  else storeRemove(ENDPOINT_KEY);
  return getEndpoint();
}

function aggregatePayload(now) {
  const st = getStats();
  return {
    v: 1,
    ts: now,
    counters: st.counters,
    modules: st.modules,
    failures: st.failures,
    total: st.total,
    added: st.added,
    starts: st.starts,
    runs: st.runs,
    avgMs: st.avgMs,
    abandoned: st.abandoned,
    abandonRate: Number(st.abandonRate.toFixed(4)),
    uploadsNotStarted: Number(st.uploadsNotStarted.toFixed(4)),
    desktop: st.desktop,
  };
}

export async function flush({ force = false, fetchImpl, now } = {}) {
  if (!isEnabled()) return { sent: false, reason: "disabled" };
  const url = getEndpoint();
  if (!url) return { sent: false, reason: "no-endpoint" };
  const ts = now || Date.now();
  const last = Number(storeGet(SENT_KEY)) || 0;
  if (!force && last > 0 && ts - last < MIN_INTERVAL_MS) return { sent: false, reason: "throttled" };
  const doFetch = fetchImpl || (typeof fetch === "function" ? fetch : null);
  if (!doFetch) return { sent: false, reason: "no-fetch" };
  try {
    const res = await doFetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(aggregatePayload(ts)),
      keepalive: true,
    });
    if (res && res.ok === false) return { sent: false, reason: `http-${res.status || 0}` };
    storeSet(SENT_KEY, String(ts));
    return { sent: true };
  } catch {
    return { sent: false, reason: "error" };
  }
}
