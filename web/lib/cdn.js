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
