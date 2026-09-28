export function jsDelivr(pkgPath) {
  return `https://cdn.jsdelivr.net/npm/${pkgPath}`;
}

export function unpkg(pkgPath) {
  return `https://unpkg.com/${pkgPath}`;
}

export const JSZIP_URLS = [
  jsDelivr("jszip@3.10.1/dist/jszip.min.js"),
  unpkg("jszip@3.10.1/dist/jszip.min.js"),
];

export const GIFUCT_URLS = [
  jsDelivr("gifuct-js@2.1.2/+esm"),
  "https://esm.sh/gifuct-js@2.1.2",
];

export const FFMPEG_URLS = [
  jsDelivr("@ffmpeg/ffmpeg@0.12.10/dist/umd/ffmpeg.js"),
  unpkg("@ffmpeg/ffmpeg@0.12.10/dist/umd/ffmpeg.js"),
];

export const FFMPEG_WORKER_URLS = [
  jsDelivr("@ffmpeg/ffmpeg@0.12.10/dist/umd/814.ffmpeg.js"),
  unpkg("@ffmpeg/ffmpeg@0.12.10/dist/umd/814.ffmpeg.js"),
];

export const FFMPEG_UTIL_URLS = [
  jsDelivr("@ffmpeg/util@0.12.1/dist/umd/index.js"),
  unpkg("@ffmpeg/util@0.12.1/dist/umd/index.js"),
];

export const FFMPEG_CORE_JS_URLS = [
  jsDelivr("@ffmpeg/core@0.12.6/dist/esm/ffmpeg-core.js"),
  unpkg("@ffmpeg/core@0.12.6/dist/esm/ffmpeg-core.js"),
];

export const FFMPEG_CORE_WASM_URLS = [
  jsDelivr("@ffmpeg/core@0.12.6/dist/esm/ffmpeg-core.wasm"),
  unpkg("@ffmpeg/core@0.12.6/dist/esm/ffmpeg-core.wasm"),
];

// SRI pin（sha384）for the script-tag injected UMD bundles. Both mirrors serve
// byte-identical npm dist files (verified by scripts/check_cdn.mjs on every
// push), so one hash covers jsDelivr and unpkg. Dynamic import() has no
// integrity parameter — the ESM deps (gifuct) and the toBlobURL-fetched
// ffmpeg core stay pinned by exact URL version instead.
export const SCRIPT_INTEGRITY = {
  [jsDelivr("jszip@3.10.1/dist/jszip.min.js")]:
    "sha384-+mbV2IY1Zk/X1p/nWllGySJSUN8uMs+gUAN10Or95UBH0fpj6GfKgPmgC5EXieXG",
  [unpkg("jszip@3.10.1/dist/jszip.min.js")]:
    "sha384-+mbV2IY1Zk/X1p/nWllGySJSUN8uMs+gUAN10Or95UBH0fpj6GfKgPmgC5EXieXG",
  [jsDelivr("@ffmpeg/ffmpeg@0.12.10/dist/umd/ffmpeg.js")]:
    "sha384-HJcOheArWWImG8iIDY0pbuK4nyRXZYGkzfaCq+ghw2CcjBlDShKWGpC9sTL42Lcu",
  [unpkg("@ffmpeg/ffmpeg@0.12.10/dist/umd/ffmpeg.js")]:
    "sha384-HJcOheArWWImG8iIDY0pbuK4nyRXZYGkzfaCq+ghw2CcjBlDShKWGpC9sTL42Lcu",
  [jsDelivr("@ffmpeg/ffmpeg@0.12.10/dist/umd/814.ffmpeg.js")]:
    "sha384-FbQ8Kru8R64sYInfholnDBqLYOCaBYZ4dig9JygFkoVZfRBndt7WQJo6CSCeono9",
  [unpkg("@ffmpeg/ffmpeg@0.12.10/dist/umd/814.ffmpeg.js")]:
    "sha384-FbQ8Kru8R64sYInfholnDBqLYOCaBYZ4dig9JygFkoVZfRBndt7WQJo6CSCeono9",
  [jsDelivr("@ffmpeg/util@0.12.1/dist/umd/index.js")]:
    "sha384-77TSno5UBOIFbP0dHjJN2umKfrf22jDQ8tKw2BfJqKvoJfUsWnmtW6a5LlkDVdNu",
  [unpkg("@ffmpeg/util@0.12.1/dist/umd/index.js")]:
    "sha384-77TSno5UBOIFbP0dHjJN2umKfrf22jDQ8tKw2BfJqKvoJfUsWnmtW6a5LlkDVdNu",
};

export function loadScriptFirst(urls, { createElement, append } = {}) {
  const create = createElement || ((tag) => document.createElement(tag));
  const attach =
    append || ((el) => document.head.appendChild(el));
  return urls.reduce(
    (chain, url) =>
      chain.then((loaded) => {
        if (loaded) return loaded;
        return new Promise((resolve, reject) => {
          const el = create("script");
          el.src = url;
          const integrity = SCRIPT_INTEGRITY[url];
          if (integrity) {
            el.integrity = integrity;
            el.crossOrigin = "anonymous";
          }
          el.onload = () => resolve(url);
          el.onerror = () => reject(new Error(`failed: ${url}`));
          attach(el);
        }).catch(() => null);
      }),
    Promise.resolve(null)
  ).then((loaded) => {
    if (!loaded) throw new Error(`all mirrors failed: ${urls.join(", ")}`);
    return loaded;
  });
}

export function importFirst(urls) {
  return urls.reduce(
    (chain, url) =>
      chain.then((mod) => {
        if (mod) return mod;
        return import(url).catch(() => null);
      }),
    Promise.resolve(null)
  ).then((mod) => {
    if (!mod) throw new Error(`all mirrors failed: ${urls.join(", ")}`);
    return mod;
  });
}

const scriptPromises = new Map();

// loadScriptFirst with in-flight dedupe: concurrent callers of the same URL
// list share one injection, and a failed attempt is not cached
export function loadScriptFirstOnce(urls, opts) {
  const key = urls.join("|");
  if (!scriptPromises.has(key)) {
    const p = loadScriptFirst(urls, opts).catch((e) => {
      scriptPromises.delete(key);
      throw e;
    });
    scriptPromises.set(key, p);
  }
  return scriptPromises.get(key);
}

export async function toBlobUrlFirst(urls, mime, toBlobURL) {
  let last;
  for (const url of urls) {
    try {
      return await toBlobURL(url, mime);
    } catch (e) {
      last = e;
    }
  }
  throw new Error(`all mirrors failed: ${urls.join(", ")} (${last || "no attempt"})`);
}
