// web/lib/sw_core.js
// Service worker strategy helpers. Classic script: importScripts'd by web/sw.js
// (exposed as self.__wcCore) and imported by node tests (globalThis.__wcCore).
(function (g) {
  "use strict";
  const CACHE_PREFIX = "wc-shell-";

  function cacheName(version) {
    return CACHE_PREFIX + version;
  }

  function isNavigationRequest(request) {
    return request.mode === "navigate" || request.destination === "document";
  }

  function isCacheableResponse(request, response) {
    if (!request || request.method !== "GET") return false;
    if (!response || !response.ok) return false;
    if (response.type === "opaque" || response.type === "opaqueredirect") return false;
    if (response.status === 206) return false;
    let url;
    try {
      url = new URL(response.url || request.url);
    } catch {
      return false;
    }
    if (url.protocol !== "http:" && url.protocol !== "https:") return false;
    if (typeof request.headers?.has === "function" && request.headers.has("range")) return false;
    return true;
  }

  g.__wcCore = { CACHE_PREFIX, cacheName, isNavigationRequest, isCacheableResponse };
})(typeof self !== "undefined" ? self : globalThis);
