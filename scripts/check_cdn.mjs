// scripts/check_cdn.mjs — HEAD-check every pinned CDN mirror declared in web/lib/cdn.js,
// and byte-verify the SRI pins in SCRIPT_INTEGRITY by hashing the real payload.
// Single source of truth: the lists come from the app itself, so a pin change or a
// dead mirror fails here instead of silently breaking the deployed web version.
import { createHash } from "node:crypto";
import {
  JSZIP_URLS,
  GIFUCT_URLS,
  FFMPEG_URLS,
  FFMPEG_WORKER_URLS,
  FFMPEG_UTIL_URLS,
  FFMPEG_CORE_JS_URLS,
  FFMPEG_CORE_WASM_URLS,
  SCRIPT_INTEGRITY,
} from "../web/lib/cdn.js";

const lists = {
  JSZIP_URLS,
  GIFUCT_URLS,
  FFMPEG_URLS,
  FFMPEG_WORKER_URLS,
  FFMPEG_UTIL_URLS,
  FFMPEG_CORE_JS_URLS,
  FFMPEG_CORE_WASM_URLS,
};

const bad = [];
let checked = 0;
for (const [name, urls] of Object.entries(lists)) {
  for (const url of urls) {
    checked += 1;
    try {
      const res = await fetch(url, { method: "HEAD", redirect: "follow" });
      if (!res.ok) bad.push(`${name}: ${res.status} ${url}`);
    } catch (e) {
      bad.push(`${name}: ERR ${url} (${e && e.message ? e.message : e})`);
    }
  }
}

// SRI byte-verify: every declared pin must match the payload every mirror serves.
let sriChecked = 0;
for (const [url, integrity] of Object.entries(SCRIPT_INTEGRITY)) {
  sriChecked += 1;
  try {
    const res = await fetch(url, { redirect: "follow" });
    if (!res.ok) {
      bad.push(`SRI: ${res.status} ${url}`);
      continue;
    }
    const digest = `sha384-${createHash("sha384")
      .update(new Uint8Array(await res.arrayBuffer()))
      .digest("base64")}`;
    if (digest !== integrity) {
      bad.push(`SRI mismatch: ${url}\n  expected ${integrity}\n  actual   ${digest}`);
    }
  } catch (e) {
    bad.push(`SRI: ERR ${url} (${e && e.message ? e.message : e})`);
  }
}

if (bad.length) {
  console.error("CDN pin failures:\n" + bad.join("\n"));
  process.exit(1);
}
console.log(
  `all ${checked} CDN pins reachable across ${Object.keys(lists).length} dependencies; ${sriChecked} SRI pins byte-verified`,
);

