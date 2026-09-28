// functions/telemetry/index.js
// HTTP Function for Wallpaper Convert opt-in anonymous telemetry.
// Contract: POST / with JSON { v, ts, counters, ...aggregates }.
// Only sanitized aggregate numbers are stored — no file names, no events.
const http = require("http");
const { URL } = require("url");
const tcb = require("@cloudbase/node-sdk");

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

const MAX_BODY_BYTES = 16 * 1024;
const MAX_COUNTER_KEYS = 64;
const COUNTER_KEY_RE = /^[a-zA-Z0-9:_-]{1,64}$/;
const COLLECTION = "telemetry_events";
const SCALAR_FIELDS = ["total", "added", "starts", "runs", "avgMs", "abandoned", "desktop"];

let app = null;
function getDb() {
  if (!app) {
    app = tcb.init({
      env: process.env.TCB_ENV,
      accessKey: process.env.CLOUDBASE_APIKEY,
    });
  }
  return app.database();
}

function sendJson(res, statusCode, data) {
  res.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    ...CORS_HEADERS,
  });
  res.end(JSON.stringify(data));
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let raw = "";
    let size = 0;
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > MAX_BODY_BYTES) {
        reject(new Error("payload too large"));
        req.destroy();
        return;
      }
      raw += chunk;
    });
    req.on("end", () => {
      if (!raw) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(raw));
      } catch (e) {
        reject(e);
      }
    });
    req.on("error", reject);
  });
}

function sanitize(body) {
  const out = { v: 1, receivedAt: Date.now() };
  if (!body || typeof body !== "object" || Array.isArray(body)) return out;
  if (typeof body.ts === "number" && Number.isFinite(body.ts) && body.ts > 0) {
    out.clientTs = body.ts;
  }
  const src = body.counters;
  if (src && typeof src === "object" && !Array.isArray(src)) {
    const counters = {};
    let kept = 0;
    for (const [k, val] of Object.entries(src)) {
      if (kept >= MAX_COUNTER_KEYS) break;
      if (
        typeof val === "number" &&
        Number.isFinite(val) &&
        COUNTER_KEY_RE.test(k)
      ) {
        counters[k] = val;
        kept += 1;
      }
    }
    out.counters = counters;
  }
  for (const key of SCALAR_FIELDS) {
    const v = body[key];
    if (typeof v === "number" && Number.isFinite(v)) out[key] = v;
  }
  return out;
}

const server = http.createServer(async (req, res) => {
  if (req.method === "OPTIONS") {
    res.writeHead(204, CORS_HEADERS);
    res.end();
    return;
  }
  const url = new URL(req.url || "/", "http://127.0.0.1");

  if (req.method === "GET" && url.pathname === "/health") {
    sendJson(res, 200, { ok: true });
    return;
  }
  if (req.method !== "POST") {
    sendJson(res, 405, { error: "method not allowed" });
    return;
  }
  if (url.pathname !== "/") {
    sendJson(res, 404, { error: "not found" });
    return;
  }

  let body;
  try {
    body = await readJsonBody(req);
  } catch (e) {
    sendJson(res, 413, { error: "payload too large" });
    return;
  }

  const doc = sanitize(body);
  try {
    await getDb().collection(COLLECTION).add(doc);
    sendJson(res, 200, { ok: true });
  } catch (e) {
    sendJson(res, 502, { error: "write failed" });
  }
});

server.listen(9000);
