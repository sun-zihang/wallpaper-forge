// web/sw.js
// Offline shell for Wallpaper Convert.
// - navigations: network-first, cached copy as offline fallback
// - static assets: stale-while-revalidate (instant paint, background refresh)
// Bump VERSION when the shell layout changes incompatibly.
/* global importScripts */
importScripts("./lib/sw_core.js");

const { cacheName, isNavigationRequest, isCacheableResponse } = self.__wcCore;
const VERSION = "1";
const CACHE = cacheName(VERSION);

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys.filter((k) => k.startsWith("wc-shell-") && k !== CACHE).map((k) => caches.delete(k)),
    );
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  if (isNavigationRequest(request)) {
    event.respondWith(networkFirst(request));
  } else {
    event.respondWith(staleWhileRevalidate(request));
  }
});

async function networkFirst(request) {
  try {
    const res = await fetch(request);
    if (isCacheableResponse(request, res)) {
      const cache = await caches.open(CACHE);
      await cache.put(request, res.clone());
    }
    return res;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    const shell =
      (await caches.match("./")) || (await caches.match("./index.html"));
    if (shell) return shell;
    return new Response("offline", {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then(async (res) => {
      if (isCacheableResponse(request, res)) {
        await cache.put(request, res.clone());
      }
      return res;
    })
    .catch(() => undefined);
  if (cached) return cached;
  const res = await network;
  if (res) return res;
  return new Response("offline", {
    status: 503,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
