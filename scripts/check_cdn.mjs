// scripts/check_cdn.mjs — HEAD-check every pinned CDN mirror declared in web/lib/cdn.js.
// Single source of truth: the lists come from the app itself, so a pin change or a
// dead mirror fails here instead of silently breaking the deployed web version.
import {
  JSZIP_URLS,
  GIFUCT_URLS,
  FFMPEG_URLS,
  FFMPEG_WORKER_URLS,
  FFMPEG_UTIL_URLS,
  FFMPEG_CORE_JS_URLS,
  FFMPEG_CORE_WASM_URLS,
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

if (bad.length) {
  console.error("unreachable CDN pins:\n" + bad.join("\n"));
  process.exit(1);
}
console.log(`all ${checked} CDN pins reachable across ${Object.keys(lists).length} dependencies`);
